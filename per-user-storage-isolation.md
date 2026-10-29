---
title: per-user-storage-isolation
status: next
priority: high
created: 2026-10-05
---

Every project on the tenant runs as one IAM role, the shared
`userflyterole`, so a notebook's own code can read and write every user's
asset files and workspace notebooks. This moves each user's files to a
bucket the shared role can't reach, behind the per-user IAM role that the
asset index already uses (ticket `dsql-asset-index`). No Union step is
needed.

The interim mitigation is [alpha-notice](alpha-notice.md): the dashboard and the
upload form tell users not to upload sensitive data.

**Not covered: Flyte's run data** (task inputs and outputs, offloaded
literals, code bundles). It stays in the tenant bucket, which every pod
reaches through the shared role. For Stargazer that's asset metadata and
store URIs, not file bytes, since tasks pass assets by reference. Moving it
needs Union to bind a role per namespace: ticket `per-user-run-data`.

## Current state

**Measured 2026-10-28** (read-only, `AWS_PROFILE=claude`):

- **The shared role reaches only three buckets.** Its S3 statement
  (managed policy `union-us-west-2-stargazerbio-userflyterole`) allows
  `GetObject*`, `PutObject*`, `DeleteObject*` and `ListBucket` on
  `union-us-west-2-stargazerbio`, `…-fast-registration` and
  `union-persistent-a6832e5930a20d18`, and nothing else in S3. Its other
  policies are ECR push and pull, IAM read and the policy simulator, and
  `PassRole` on itself. So a new bucket in the account is out of its
  reach unless a policy grants it.
- **Stargazer's files** live under
  `s3://union-us-west-2-stargazerbio/stargazer/users/<subject>/` (the
  deploys set `STARGAZER_STORE_ROOT` and `STARGAZER_WORKSPACE_ROOT` to the
  same root): `assets/`, `uploads/`, `notebooks/`, `settings.json`, plus
  Litestream's leftover `index/` and `index-lease/`. One user has a prefix:
  the test account (`u-pryce`, subject `387300641116005877`), 149 objects,
  6.06 GB.
- **One per-user role exists:** `stargazer-index-u-pryce`, trusting only
  `system:serviceaccount:u-pryce-development:default`, with one policy,
  `dsql-connect`. Onboarding (`stargazer_users.user_index` in infra) makes
  it on every call.
- Bucket names `stargazerbio-users` and `stargazer-users-791359099513` are
  free (`head-bucket` 404).

**From `dsql-asset-index`** (measured 2026-10-20): task pods and app pods
(dashboard, notebooks) both run as their namespace's `default` service
account with the projected token at `AWS_WEB_IDENTITY_TOKEN_FILE`, and a
role trusting that one namespace can be assumed from there only.

**In the code:** every read and write of the store and the workspace goes
through `flyte.storage` with the pod's default credentials:
`stargazer.utils.storage` (upload, download, exists, rm), `runtime/proxy.py`
(workspace hydrate and sync), and in infra `app/assets.py` (the dashboard's
streamed downloads and multipart uploads) and `app/workspace_store.py`.
`flyte.storage.put`, `get` and `open` don't pass per-call settings to the
store: their obstore fast path builds the store from the path alone.
`get_underlying_filesystem(path=…, **kwargs)` does pass them, and obstore's
`S3Store` takes `role_arn` and `web_identity_token_file`, assuming the role
itself and refreshing it.

## Target state

- One bucket, `stargazerbio-users`, holding each user's files at
  `users/<subject>/`, the layout they have now and have locally.
- The user's role (`stargazer-index-<project>`) gets a second policy,
  `user-store`: object read, write and delete under its own
  `users/<subject>/`, and `ListBucket` on that prefix only.
- The bucket policy denies the shared role outright and denies non-TLS
  requests. The deny holds even if Union widens the shared role's S3 grant.
- Pods keep the shared role as their default credentials, which Flyte uses
  for run data. Only Stargazer's own store and workspace calls assume the
  user's role, named by `STARGAZER_USER_ROLE_ARN`. Unset, nothing changes:
  locally, on the devbox, and in tests.

## Pieces

- [ ] **Piece 0, the tenant check**, by hand with the user's admin access
  (mine is read-only). Runbook below.
- [ ] **Piece 1, Stargazer** (this repo, one PR):
  - A helper that returns the filesystem for a store URI, with
    `STARGAZER_USER_ROLE_ARN` and the token file passed to obstore when the
    URI is `s3://` and the role is set. `StorageClient` and
    `runtime/proxy.py` use it for every store call, in place of the
    `flyte.storage` module functions. Large uploads keep flyte's part
    sizing (`_put_obstore_bypass` exists because fsspec's obstore `put`
    caps a file at ~48.8 GiB): either through the filesystem's own store
    with a computed `chunk_size`, or a different route if Piece 0 measures
    the fsspec one failing.
  - `STARGAZER_USER_ROLE_ARN` joins `_STORAGE_KEYS` in `config.py`, so runs
    started from a notebook carry it into their task pods.
  - Docs: `configuration.md` (the variable, and where hosted files live),
    `runtime.md`'s pod contract, and `runtime_internals.md`.
- [ ] **Piece 2, infra** (one PR, after Piece 1's release):
  - `aws/storage.tf`: the bucket, imported from Piece 0, with versioning,
    Block Public Access, SSE-S3, the lifecycle rule and the bucket policy.
    `tenant.env`'s `STARGAZER_WORKSPACE_ROOT` becomes `s3://stargazerbio-users`.
  - Onboarding puts `user-store` on the role, scoped to the user's
    subject, and offboarding deletes it before the role.
  - Deploys: dashboards and notebook pods get `STARGAZER_USER_ROLE_ARN`
    (the role ARN `app.deploy` already builds for the index URL).
    `app/assets.py` and `app/workspace_store.py` use Stargazer's helper.
- [ ] **Piece 3, migration** (admin, after Piece 2 deploys):
  - Copy the test account's `assets/`, `uploads/`, `notebooks/` and
    `settings.json` to `s3://stargazerbio-users/users/387300641116005877/`.
  - Rewrite its index rows: `uri` prefix
    `s3://union-us-west-2-stargazerbio/stargazer/` →
    `s3://stargazerbio-users/` in `assets.u_pryce`, as the DSQL admin.
  - Delete the old `stargazer/users/` prefix once the dashboard and a
    notebook read from the new one.
  - Update [alpha-notice](alpha-notice.md): uploaded files are now private,
    and run data isn't.

**Verified when**, on the test account:
- The germline workflow runs end to end, started from a notebook, with its
  outputs in the new bucket.
- The dashboard uploads, lists and downloads an asset; a notebook's
  workspace survives a restart.
- From a notebook cell, the pod's default credentials get `AccessDenied` on
  the bucket, and the user's role gets `AccessDenied` on another user's
  prefix.

## Design decisions

1. **One bucket with a prefix per user, not a bucket per user.** The role
   policy names the prefix as precisely as it would name a bucket.
   Onboarding stays IAM-only, with no per-user bucket, CORS, lifecycle or
   policy to create, and the layout stays the one local runs use
   (D6 below). Per-user cost and deletion work by prefix.
2. **The index's role gets the storage policy.** One role per user for
   everything that's theirs. The name says `index` for now; renaming it
   means new roles and new DSQL mappings for no change in access.
3. **Only Stargazer's calls assume the role.** Overriding `AWS_ROLE_ARN`
   for the whole pod would move Flyte's own I/O onto the user's role, which
   would then need a copy of Union's grants, kept in step with theirs.
   Also, the pod-identity webhook doesn't inject the token into a
   container that already sets `AWS_ROLE_ARN` (inferred from its source,
   not measured).
4. **Deny the shared role in the bucket policy**, not only leave it
   ungranted. It costs one statement and survives a broader Union grant.

## Settled questions

The open questions from 2026-10-07, against this design:
- **D1, can Union's role binding be automated?** Not needed for storage.
  It still blocks run data (ticket `per-user-run-data`).
- **D2, do app pods get the bound role?** Measured yes (above).
- **D3, what else does a user role need?** Nothing: pods keep the shared
  role for Union's buckets.
- **D4, do per-project `storage.raw_data_path` and `run.run_base_dir` move
  run data?** Moved to `per-user-run-data`.
- **D5, who creates buckets and roles?** Tofu makes the one bucket.
  Onboarding already runs with the admin's AWS credentials and makes the
  role.
- **D6, keep `users/<subject>/`?** Yes (decision 1).

## Piece 0 runbook

For the user's admin profile (`pryce`), in zsh, from any directory
outside the repo. It takes minutes, plus one image build on the first
`flyte run`. Values measured 2026-10-28 with `AWS_PROFILE=claude`.

**0. Shell.**

```bash
aws sso login --profile pryce
export AWS_PROFILE=pryce AWS_REGION=us-west-2
REPO=~/Desktop/stargazerbio/stargazer
BUCKET=stargazerbio-users
SUBJECT=387300641116005877
ROLE=stargazer-index-u-pryce
ROLE_ARN=arn:aws:iam::791359099513:role/$ROLE
SHARED_ARN=arn:aws:iam::791359099513:role/union-us-west-2-stargazerbio-userflyterole
mkdir -p /tmp/store-probe && cd /tmp/store-probe
```

**1. The bucket.** New buckets already block public access and encrypt
with SSE-S3; both are set explicitly so tofu can import them as they are.

```bash
aws s3api create-bucket --bucket "$BUCKET" --create-bucket-configuration LocationConstraint=us-west-2
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --lifecycle-configuration '{"Rules":[{"ID":"expire-noncurrent","Status":"Enabled","Filter":{},"NoncurrentVersionExpiration":{"NoncurrentDays":30},"AbortIncompleteMultipartUpload":{"DaysAfterInitiation":7}}]}'
cat > bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": ["arn:aws:s3:::${BUCKET}", "arn:aws:s3:::${BUCKET}/*"],
      "Condition": {"Bool": {"aws:SecureTransport": "false"}}
    },
    {
      "Sid": "DenySharedPodRole",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": ["arn:aws:s3:::${BUCKET}", "arn:aws:s3:::${BUCKET}/*"],
      "Condition": {"ArnEquals": {"aws:PrincipalArn": "${SHARED_ARN}"}}
    }
  ]
}
EOF
aws s3api put-bucket-policy --bucket "$BUCKET" --policy file://bucket-policy.json
```

**2. The user's storage policy.** `s3:prefix` is set on `ListObjectsV2`
only, so a `HeadObject` on a missing key may be refused (403) instead of
not found (404). The probe measures it, since `StorageClient.upload` asks
whether a file exists before it writes.

```bash
cat > user-store.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "OwnObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
      "Resource": "arn:aws:s3:::${BUCKET}/users/${SUBJECT}/*"
    },
    {
      "Sid": "ListOwnPrefix",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::${BUCKET}",
      "Condition": {"StringLike": {"s3:prefix": ["users/${SUBJECT}/*"]}}
    }
  ]
}
EOF
aws iam put-role-policy --role-name "$ROLE" --policy-name user-store --policy-document file://user-store.json
echo other | aws s3 cp - "s3://$BUCKET/users/other/probe.txt"
```

`users/other/probe.txt` stands in for another user's file.

**3. The probe from task pods.** Save the block below as
`/tmp/store-probe/store_probe.py`. Its image is Flyte's Debian base, which
already carries obstore (a dependency of flyte).

```python
"""Piece 0 probe for ticket per-user-storage-isolation: the user's prefix from a task pod."""

import base64
import json
import os
import time
from pathlib import Path

import flyte
import flyte.storage
import obstore
from obstore.store import S3Store

BUCKET = "stargazerbio-users"
REGION = "us-west-2"
env = flyte.TaskEnvironment(
    name="store_probe",
    image=flyte.Image.from_debian_base(name="store-probe", platform=("linux/amd64",)),
    resources=flyte.Resources(cpu=1, memory="1Gi"),
)


def _try(fn):
    """fn's result ('ok' for None), or the error it raised."""
    try:
        out = fn()
        return "ok" if out is None else out
    except Exception as err:
        return f"{type(err).__name__}: {str(err)[:300]}"


def _timed(fn):
    """fn's result and its wall time in ms."""
    t0 = time.perf_counter()
    out = _try(fn)
    return out, round((time.perf_counter() - t0) * 1000)


def _checks(store: S3Store, subject: str) -> dict:
    """Every call StorageClient and the workspace sync make, on the user's prefix and another's."""
    own = f"users/{subject}/probe"
    big = os.urandom(12 * 1024 * 1024)
    out = {}
    out["own_put"], out["first_call_ms"] = _timed(lambda: obstore.put(store, f"{own}/a.txt", b"hello") and None)
    out["own_put_again"], out["second_call_ms"] = _timed(lambda: obstore.put(store, f"{own}/b.txt", b"hi") and None)
    out["own_get"] = _try(lambda: bytes(obstore.get(store, f"{own}/a.txt").bytes()).decode())
    out["own_head"] = _try(lambda: obstore.head(store, f"{own}/a.txt")["size"])
    out["own_head_missing"] = _try(lambda: obstore.head(store, f"{own}/missing.txt"))
    out["own_list"] = _try(lambda: sorted(m["path"] for b in obstore.list(store, f"users/{subject}/") for m in b))
    out["own_multipart_12MiB"] = _try(lambda: obstore.put(store, f"{own}/big.bin", big, chunk_size=5 * 1024 * 1024) and None)
    out["own_multipart_size"] = _try(lambda: obstore.head(store, f"{own}/big.bin")["size"])
    out["own_delete"] = _try(lambda: [obstore.delete(store, f"{own}/{n}") for n in ("a.txt", "b.txt", "big.bin")] and None)
    out["other_get"] = _try(lambda: bytes(obstore.get(store, "users/other/probe.txt").bytes()).decode())
    out["other_put"] = _try(lambda: obstore.put(store, "users/other/x.txt", b"x") and None)
    out["other_list"] = _try(lambda: [m["path"] for b in obstore.list(store, "users/other/") for m in b])
    out["root_list"] = _try(lambda: [m["path"] for b in obstore.list(store, "users/") for m in b])
    return out


@env.task
def probe(role_arn: str, subject: str) -> str:
    """The user's role on its own prefix and another's; the pod's default role on both."""
    token_file = os.environ["AWS_WEB_IDENTITY_TOKEN_FILE"]
    claims = json.loads(base64.urlsafe_b64decode(Path(token_file).read_text().split(".")[1] + "=="))
    report = {"sub": claims["sub"], "aud": claims["aud"]}
    user = S3Store(BUCKET, region=REGION, role_arn=role_arn, web_identity_token_file=token_file)
    report["user_role"] = _checks(user, subject)
    shared = S3Store(BUCKET, region=REGION)
    report["shared_role"] = {
        "put": _try(lambda: obstore.put(shared, f"users/{subject}/probe/s.txt", b"s") and None),
        "get_other": _try(lambda: bytes(obstore.get(shared, "users/other/probe.txt").bytes()).decode()),
        "list": _try(lambda: [m["path"] for b in obstore.list(shared, "users/") for m in b]),
    }
    uri = f"s3://{BUCKET}/users/{subject}/probe/fsspec.txt"
    fs = flyte.storage.get_underlying_filesystem(
        path=uri, config={"role_arn": role_arn, "web_identity_token_file": token_file, "region": REGION}
    )
    report["fsspec"] = {
        "type": type(fs).__name__,
        "pipe": _try(lambda: fs.pipe_file(uri, b"via fsspec")),
        "cat": _try(lambda: fs.cat_file(uri).decode()),
        "exists": _try(lambda: fs.exists(uri)),
        "exists_missing": _try(lambda: fs.exists(uri + ".missing")),
        "rm": _try(lambda: fs.rm(uri)),
    }
    print(json.dumps(report, indent=2))
    return json.dumps(report)
```

```bash
flyte_probe() { uv run --project "$REPO" python -c 'import sys; from flyte.cli.main import main; sys.argv[0] = "flyte"; main()' --config "$REPO/.flyte/union.yaml" "$@"; }
flyte_probe run --follow -p u-pryce -d development store_probe.py probe --role_arn "$ROLE_ARN" --subject "$SUBJECT"
flyte_probe run --follow -p flytesnacks -d development store_probe.py probe --role_arn "$ROLE_ARN" --subject "$SUBJECT"
flyte_probe get run --in-phase running -p u-pryce -d development
flyte_probe get run --in-phase running -p flytesnacks -d development
```

Each run prints a JSON report and returns it. What to expect:
- Both: `shared_role` refused everywhere (`DenySharedPodRole`).
- `flytesnacks`: every `user_role` and `fsspec` call refused, since STS
  won't let that namespace assume the role.
- `u-pryce`:
  - `own_put`, `own_put_again`, `own_get` (`hello`), `own_head` (`5`),
    `own_list` (both keys), `own_multipart_12MiB` and
    `own_multipart_size` (`12582912`), `own_delete`: ok.
  - `own_head_missing`: not found, or refused (see step 2). Refused means
    the `ListBucket` grant needs a different shape before Piece 1.
  - `other_get`, `other_put`, `other_list`, `root_list`: refused.
  - `first_call_ms` minus `second_call_ms`: about what the STS call adds.
  - `fsspec`: `pipe`, `cat` (`via fsspec`), `exists` (`True`),
    `exists_missing` (`False`) and `rm` succeed. This is the route Piece 1
    takes. If it fails while the direct `S3Store` works, Piece 1 builds the
    `S3Store` itself.

**4. Record** under `## Piece 0 results (<date>)`: both reports verbatim
with their run names, and anything refused or changed along the way. Then
tick Piece 0.

**Afterwards.** Keep the bucket and the role's `user-store` policy: Piece 2
imports the bucket into tofu and onboarding takes over the policy. Remove
the stand-in file and its versions:

```bash
aws s3api list-object-versions --bucket "$BUCKET" --prefix users/other/ --query '{Objects: Versions[].{Key: Key, VersionId: VersionId}}' --output json > other.json
aws s3api delete-objects --bucket "$BUCKET" --delete file://other.json
```

**Measured locally (2026-10-28):** the probe's `_checks` against an
in-memory obstore store make every call as written (put, get, head,
list, a 12 MiB multipart put, delete); `S3Store` accepts `role_arn` and
`web_identity_token_file`; and `flyte.storage.get_underlying_filesystem`
with `config=` builds an `FsspecStore_s3` whose store carries both.

**Unverified**, settled by the runbook's own output: whether obstore
assumes the role on the tenant, the bucket and role policies' refusals,
the missing-key `HeadObject` status, the fsspec calls against S3, and
whether the remote builder builds the probe image as written.

## Earlier notes

**A bucket per user** was the 2026-10-08 design, deferred from plan 28
(now [asset-manager-on-index](asset-manager-on-index.md)): each project
running as its own role, bound by Union, with a bucket per user. It needed
Union to bind each new project's role (D1), and a bucket alone isn't
isolation while every project shares a role that reaches it. Decision 1
replaces it.
