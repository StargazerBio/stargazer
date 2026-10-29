---
title: per-user-storage-isolation
status: doing
priority: high
created: 2026-10-05
---

Every project on the tenant runs as one IAM role, the shared
`userflyterole`, which reaches the whole tenant bucket. So a user's own code,
in a notebook or a task, can list, read, overwrite and delete every other
user's asset files, workspace notebooks and run data (task inputs and
outputs, and files Flyte uploads). Union's RBAC doesn't help: it guards
Union's API, and pods talk to S3 directly.

This makes everything a user's project writes land, by default, in a
bucket only that user's role can reach:

- **A bucket the shared role can't reach**, `stargazerbio-users`, with each
  user's files under `users/<subject>/`.
- **One IAM role per user**, holding everything that's theirs alone.
- **Their project's pods run as that role by default**, and the project's
  Flyte settings point run data into their prefix.

No Union step is needed. The shared role stays, and any pod can still
assume it, but nothing of anyone's is in its reach unless they write to
the tenant bucket on purpose.

The interim mitigation is [alpha-notice](alpha-notice.md): the dashboard and the
upload form tell users not to upload sensitive data.

## Current state

**Measured 2026-10-28** (read-only: `AWS_PROFILE=claude`, kubectl through
`stargazer-eks-access`, `flyte get`):

- **Union's two roles reach only three buckets.** The shared pod role
  (`union-us-west-2-stargazerbio-userflyterole`) and Union's own services'
  role (`…-adminflyterole`) both allow `GetObject*`, `PutObject*`,
  `DeleteObject*` and `ListBucket` on `union-us-west-2-stargazerbio`,
  `…-fast-registration` and `union-persistent-a6832e5930a20d18`, and
  nothing else in S3. So a new bucket is out of their reach unless a policy
  grants it. The shared role trusts `system:serviceaccount:*:*`.
- **Run data** lives in the tenant bucket at
  `metadata/v2/stargazerbio/<project>/<domain>/<run>/<action>/…`:
  `inputs.pb`, and per attempt `outputs.pb` and any files the task wrote
  (an `admin` run's `report.html`). Every `u-pryce` run so far holds only
  `.pb` files.
- **Per-project settings** (`flyte get settings -p u-pryce -d
  development`): `run.run_base_dir` ("base directory for run metadata such
  as inputs/outputs"), `storage.raw_data_path` and `environment_variables`
  ("environment variables injected into task pods") are all empty, so the
  org defaults apply.
- **Stargazer's files** live under
  `s3://union-us-west-2-stargazerbio/stargazer/users/<subject>/` (the
  deploys set `STARGAZER_STORE_ROOT` and `STARGAZER_WORKSPACE_ROOT` to that
  root): `assets/`, `uploads/`, `notebooks/`, `settings.json`, plus
  Litestream's leftover `index/` and `index-lease/`. One user has a prefix:
  the test account (`u-pryce`, subject `387300641116005877`), 149 objects,
  6.06 GB.
- **One per-user role exists:** `stargazer-index-u-pryce`, trusting only
  `system:serviceaccount:u-pryce-development:default` with audience
  `sts.amazonaws.com`, with one policy, `dsql-connect`. Onboarding
  (`stargazer_users.user_index` in infra) makes it on every call.
- **The token webhook is EKS's managed `pod-identity-webhook`**
  (a `MutatingWebhookConfiguration` with no deployment in the cluster).
  Its source (`aws/amazon-eks-pod-identity-webhook`, `master`,
  `pkg/handler/handler.go`) keeps a container's own `AWS_ROLE_ARN` and
  `AWS_WEB_IDENTITY_TOKEN_FILE` and still mounts the projected token,
  unless the container also sets both `AWS_REGION` and
  `AWS_STS_REGIONAL_ENDPOINTS`. Which version EKS runs isn't visible.
- `u-pryce` holds a `development` secret `UNION_API_KEY`, so its pods can
  launch child actions. Bucket name `stargazerbio-users` is free.

**From `dsql-asset-index`** (measured 2026-10-20): task pods and app pods
(dashboard, notebooks) both run as their namespace's `default` service
account, with the projected token at
`/var/run/secrets/eks.amazonaws.com/serviceaccount/token`, and a role
trusting that one namespace can be assumed from there only.

**In the code:** Stargazer's store and workspace calls, and Flyte's own
I/O, all go through obstore with the pod's default credentials:
`stargazer.utils.storage`, `runtime/proxy.py`, and in infra
`app/assets.py` and `app/workspace_store.py`. obstore reads
`AWS_ROLE_ARN` and `AWS_WEB_IDENTITY_TOKEN_FILE` like every AWS SDK, so
changing the pod's default role moves all of them at once.

## Target state

- **The bucket** `stargazerbio-users`, with Block Public Access,
  versioning, SSE-S3 and a noncurrent-version expiry. Each user's files
  sit under `users/<subject>/`: Stargazer's (`assets/`, `uploads/`,
  `notebooks/`, `settings.json`) and Flyte's (`flyte/runs/`, `flyte/raw/`).
- **Its bucket policy** grants each role tagged `stargazer-subject` object
  read, write and delete under `users/<that subject>/`, and `ListBucket` on
  that prefix only, so no per-user policy names the bucket. It denies the
  shared role outright, denies non-TLS requests, and allows Union's
  services (`adminflyterole`) the `users/*/flyte/` prefixes, so the console
  and executor still read inputs and outputs. Union's roles themselves are
  untouched.
- **One IAM role per user,** `stargazer-user-<project>`, replacing
  `stargazer-index-<project>`, tagged `stargazer-subject=<subject>`, with:
  - `dsql-connect`: their index table, as today.
  - `stargazer-user-union-read`, a managed policy shared by every user's
    role: read on Union's three buckets, for code bundles and anything else
    Flyte reads there.
  - Anything per-user later becomes another policy on it.
- **All of it is code:** the bucket, its policy and the managed policy in
  infra's tofu stack (`aws/storage.tf`), each user's role, tag and
  attachment in onboarding.
- **Each user's project settings:** `run.run_base_dir` and
  `storage.raw_data_path` point into their `flyte/` prefix, and
  `environment_variables` sets `AWS_ROLE_ARN` to their role and
  `AWS_WEB_IDENTITY_TOKEN_FILE` to the token path, for every task pod.
- **App pods** (dashboard, notebooks) get the same two variables from
  their deploys, since the project setting reaches task pods only.
- **Stargazer's code doesn't change:** its calls use the pod's default
  credentials, which are now the user's role. Its deploys point
  `STARGAZER_STORE_ROOT` and `STARGAZER_WORKSPACE_ROOT` at the bucket.

## Pieces

- [ ] **Piece 0, the tenant check.** Part A by the user's admin profile
  (my AWS access is read-only), Part B by me. Runbook below.
- [ ] **Piece 1, infra** (one PR, branch `feat/per-user-storage-isolation`):
  - [x] `aws/storage.tf`: the bucket, its policy and
    `stargazer-user-union-read` (commit `d2688dc`; plan below).
  - [x] Onboarding tags the role with the user's subject and attaches
    `stargazer-user-union-read`; offboarding detaches it before deleting
    the role (commit `d2688dc`).
  - [ ] `tenant.env`'s `STARGAZER_WORKSPACE_ROOT` becomes
    `s3://stargazerbio-users`.
  - [ ] Onboarding makes `stargazer-user-<project>` in place of
    `stargazer-index-<project>` (`app.deploy.iam_role_name`). The
    role-making code moves out of `stargazer_users.user_index` into a
    module of its own, since it's no longer the index's. A new role
    already gets its DSQL login mapped afresh.
  - [ ] Onboarding applies the project's three settings.
  - [ ] Deploys: dashboards and notebook pods get `AWS_ROLE_ARN` and
    `AWS_WEB_IDENTITY_TOKEN_FILE`. The index URL's `role_arn` is the same
    ARN.
  - [ ] The rename, once: re-onboard `u-pryce`, then have offboarding's
    code remove `stargazer-index-u-pryce` and its DSQL mapping.
- [ ] **Piece 2, Stargazer docs** (one PR): `configuration.md` (where
  hosted files and run data live), `runtime.md`'s pod contract (pods run
  as the user's role), `runtime_internals.md`. If Piece 0 shows the
  pod-wide role doesn't work, this piece instead gives Stargazer's own
  calls the role (obstore's `S3Store` takes `role_arn` and
  `web_identity_token_file`, and `flyte.storage.get_underlying_filesystem`
  passes `config=` through to it, measured locally), and run data stays
  exposed.
- [ ] **Piece 3, migration** (admin, after Piece 1 deploys):
  - Copy the test account's `assets/`, `uploads/`, `notebooks/` and
    `settings.json` to `s3://stargazerbio-users/users/387300641116005877/`.
  - Rewrite its index rows: `uri` prefix
    `s3://union-us-west-2-stargazerbio/stargazer/` →
    `s3://stargazerbio-users/` in `assets.u_pryce`, as the DSQL admin.
  - Delete the old `stargazer/users/` prefix once the dashboard and a
    notebook read from the new one. Past runs' data in
    `metadata/v2/stargazerbio/u-pryce/` stays where it is.
  - Update [alpha-notice](alpha-notice.md) to match.

**Verified when**, on the test account:
- The germline workflow runs end to end, started from a notebook, with its
  run data and outputs under the user's prefix and nothing new in the
  tenant bucket.
- The dashboard uploads, lists and downloads an asset; a notebook's
  workspace survives a restart; the console shows a run's inputs and
  outputs.
- From a notebook cell, the shared role (assumed with the pod's token) gets
  `AccessDenied` on the user's prefix, and the user's role gets
  `AccessDenied` on another user's.

## Design decisions

1. **One bucket with a prefix per user, not a bucket per user.** The role
   policy names the prefix as precisely as it would name a bucket.
   Onboarding stays IAM and settings only, and the layout stays the one
   local runs use. Per-user cost and deletion work by prefix.
2. **One role per user for everything that's theirs,** named for the user
   rather than the index. Renaming costs a new role and DSQL mapping per
   existing user, and there is one (`u-pryce`), so it's cheapest now.
   Piece 0 uses the existing `stargazer-index-u-pryce`, since a policy
   behaves the same whatever its role's name.
3. **Pods default to the user's role,** so Flyte's run data and
   Stargazer's files are both private without any code knowing about roles.
   Private is the default; sharing takes a deliberate write with the
   shared role.
4. **Union's roles stay untouched.** Their services get in through our
   bucket's policy, and the user's role gets read on their buckets.
5. **Deny the shared role in the bucket policy**, not only leave it
   ungranted. It costs one statement and survives a broader Union grant.
6. **The bucket policy grants each prefix by the role's subject tag**
   (`${aws:PrincipalTag/stargazer-subject}`), so tofu owns every statement
   that names the bucket and onboarding only tags and attaches. A
   per-user inline policy would have put the bucket's access rules in two
   places. Its `Allow` to `*` is pinned to the account by
   `aws:PrincipalAccount`, which Block Public Access requires, and an
   untagged principal leaves the variable unresolved, so it matches
   nothing.
7. **Every AWS change is code.** Shared resources in tofu, per-user ones in
   onboarding; no hand-run `aws` commands, Piece 0 included.

## Piece 0 runbook

The runs need Part A first: with the settings in place and no bucket,
every `u-pryce` run would fail.

### Part A: AWS, by the user's admin profile

Everything here is code on infra's `feat/per-user-storage-isolation`
branch, in the worktree `.claude/worktrees/per-user-storage-isolation`.

**1. Apply the stack.** The stack's state lives in the main checkout's
`aws/terraform.tfstate`; the worktree holds a copy of it, so copy it back
after applying.

```bash
cd ~/Desktop/stargazerbio/infra/.claude/worktrees/per-user-storage-isolation/aws
aws sso login --profile pryce
AWS_PROFILE=pryce AWS_REGION=us-west-2 ../tofu.sh apply
cp terraform.tfstate ~/Desktop/stargazerbio/infra/aws/terraform.tfstate
```

It should show `Plan: 7 to add, 0 to change, 0 to destroy` (the plan I ran
with `AWS_PROFILE=claude` on 2026-10-28): the bucket, its public access
block, encryption, versioning, lifecycle and policy, and the managed policy
`stargazer-user-union-read`. The bucket policy renders the prefix as
`users/${aws:PrincipalTag/stargazer-subject}` (checked in `tofu console`).

**2. Re-run onboarding's role step for the test account,** from the same
branch, so `stargazer-index-u-pryce` gets its subject tag and the managed
policy. `upgrade` ensures the index (role included) and redeploys the
dashboard.

```bash
cd ~/Desktop/stargazerbio/infra/.claude/worktrees/per-user-storage-isolation
AWS_PROFILE=pryce ./stargazer-users upgrade --email pryce@stargazer.bio
```

Then tell me Part A is done, with anything that was refused. I check the
role's tag and attachment read-only, and stop the dashboard `upgrade`
woke once Part B is done.

### Part B: Flyte, by me

From the main checkout, with `.flyte/union.yaml`. Each step's result is
recorded under `## Piece 0 results`.

**3. The project's settings,** from a file
(`flyte edit settings --from-file` prints the diff and applies it):

```yaml
run.run_base_dir: s3://stargazerbio-users/users/387300641116005877/flyte/runs
storage.raw_data_path: s3://stargazerbio-users/users/387300641116005877/flyte/raw
environment_variables:
  AWS_ROLE_ARN: arn:aws:iam::791359099513:role/stargazer-index-u-pryce
  AWS_WEB_IDENTITY_TOKEN_FILE: /var/run/secrets/eks.amazonaws.com/serviceaccount/token
```

```bash
flyte --config .flyte/union.yaml edit settings -p u-pryce -d development --from-file isolation-settings.yaml
flyte --config .flyte/union.yaml get settings -p u-pryce -d development
```

**4. The probe,** saved as `isolation_probe.py`: `probe` in `u-pryce`
calls a child task that returns a `File` without a destination, then
checks who the pod is and who reaches what; `outsider` in `flytesnacks`
checks the same prefix from another project. Its image is Flyte's Debian
base plus boto3; obstore comes with flyte.

```python
"""Piece 0 probe for ticket per-user-storage-isolation: a project's pods on their user's role."""

import base64
import json
import os
import tempfile
from pathlib import Path

import boto3
import flyte
import obstore
from flyte.io import File
from obstore.store import S3Store

BUCKET = "stargazerbio-users"
TENANT_BUCKET = "union-us-west-2-stargazerbio"
SHARED_ROLE = "arn:aws:iam::791359099513:role/union-us-west-2-stargazerbio-userflyterole"
REGION = "us-west-2"
image = flyte.Image.from_debian_base(name="isolation-probe", platform=("linux/amd64",)).with_pip_packages(
    "boto3>=1.35,<2"
)
env = flyte.TaskEnvironment(
    name="isolation_probe",
    image=image,
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    secrets=[flyte.Secret(key="UNION_API_KEY", as_env_var="_UNION_EAGER_API_KEY")],
)
outsider_env = flyte.TaskEnvironment(
    name="isolation_outsider", image=image, resources=flyte.Resources(cpu=1, memory="1Gi")
)


def _try(fn):
    """fn's result ('ok' for None), or the error it raised."""
    try:
        out = fn()
        return "ok" if out is None else out
    except Exception as err:
        return f"{type(err).__name__}: {str(err)[:300]}"


def _whoami() -> dict:
    """The pod's AWS environment, its token's claims, and who STS says it is."""
    out = {
        k: os.environ.get(k)
        for k in ("AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_REGION", "AWS_STS_REGIONAL_ENDPOINTS")
    }
    token_file = Path(os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE") or "/nonexistent")
    out["token_file_exists"] = token_file.exists()
    if token_file.exists():
        claims = json.loads(base64.urlsafe_b64decode(token_file.read_text().split(".")[1] + "=="))
        out["sub"], out["aud"] = claims["sub"], claims["aud"]
    out["caller"] = _try(lambda: boto3.client("sts", region_name=REGION).get_caller_identity()["Arn"])
    return out


def _assumed_store(bucket: str, role_arn: str):
    """An S3Store signed by `role_arn`, assumed with the pod's token."""
    token = Path(os.environ["AWS_WEB_IDENTITY_TOKEN_FILE"]).read_text()
    creds = boto3.client("sts", region_name=REGION).assume_role_with_web_identity(
        RoleArn=role_arn, RoleSessionName="isolation-probe", WebIdentityToken=token
    )["Credentials"]
    return S3Store(
        bucket,
        region=REGION,
        access_key_id=creds["AccessKeyId"],
        secret_access_key=creds["SecretAccessKey"],
        session_token=creds["SessionToken"],
    )


def _paths(store, prefix: str) -> list[str]:
    """Every key under `prefix`."""
    return sorted(m["path"] for batch in obstore.list(store, prefix) for m in batch)


def _checks(store: S3Store, subject: str) -> dict:
    """The calls StorageClient and the workspace sync make, on the user's prefix and another's."""
    own = f"users/{subject}/probe"
    big = os.urandom(12 * 1024 * 1024)
    return {
        "own_put": _try(lambda: obstore.put(store, f"{own}/a.txt", b"hello") and None),
        "own_get": _try(lambda: bytes(obstore.get(store, f"{own}/a.txt").bytes()).decode()),
        "own_head": _try(lambda: obstore.head(store, f"{own}/a.txt")["size"]),
        "own_head_missing": _try(lambda: obstore.head(store, f"{own}/missing.txt")),
        "own_list": _try(lambda: _paths(store, f"{own}/")),
        "own_multipart_12MiB": _try(
            lambda: obstore.put(store, f"{own}/big.bin", big, chunk_size=5 * 1024 * 1024) and None
        ),
        "own_multipart_size": _try(lambda: obstore.head(store, f"{own}/big.bin")["size"]),
        "own_delete": _try(lambda: [obstore.delete(store, f"{own}/{n}") for n in ("a.txt", "big.bin")] and None),
        "other_get": _try(lambda: bytes(obstore.get(store, "users/other/probe.txt").bytes()).decode()),
        "other_put": _try(lambda: obstore.put(store, "users/other/x.txt", b"x") and None),
        "other_list": _try(lambda: _paths(store, "users/other/")),
        "root_list": _try(lambda: _paths(store, "users/")),
    }


@env.task
async def child(text: str) -> File:
    """A File returned with no destination, so Flyte uploads it under the raw data path."""
    path = Path(tempfile.mkdtemp()) / "child.txt"
    path.write_text(text)
    return await File.from_local(path)


@env.task
async def probe(subject: str) -> str:
    """Who the pod is, where run data lands, and who can reach it."""
    report = {"whoami": _whoami()}
    returned = await child(text="from the child task")
    report["child_file"] = returned.path
    child_key = returned.path.removeprefix(f"s3://{BUCKET}/")
    report["default_creds"] = _checks(S3Store(BUCKET, region=REGION), subject)
    report["default_creds"]["child_file_get"] = _try(
        lambda: bytes(obstore.get(S3Store(BUCKET, region=REGION), child_key).bytes()).decode()
    )
    tenant = S3Store(TENANT_BUCKET, region=REGION)
    report["tenant_bucket"] = {
        "list_own_runs": _try(lambda: len(_paths(tenant, "metadata/v2/stargazerbio/u-pryce/"))),
        "put": _try(lambda: obstore.put(tenant, "stargazer-probe/isolation.txt", b"x") and None),
    }
    shared = _try(lambda: _assumed_store(BUCKET, SHARED_ROLE))
    if isinstance(shared, S3Store):
        report["shared_role"] = {
            "child_file_get": _try(lambda: bytes(obstore.get(shared, child_key).bytes()).decode()),
            "list_own": _try(lambda: _paths(shared, f"users/{subject}/")),
        }
    else:
        report["shared_role"] = {"assume": shared}
    print(json.dumps(report, indent=2))
    return json.dumps(report)


@outsider_env.task
async def outsider(subject: str, user_role_arn: str) -> str:
    """Another project's pod: its defaults and the user's role, against the user's prefix."""
    store = S3Store(BUCKET, region=REGION)
    report = {
        "whoami": _whoami(),
        "default_list": _try(lambda: _paths(store, f"users/{subject}/")),
        "default_put": _try(lambda: obstore.put(store, f"users/{subject}/probe/outsider.txt", b"x") and None),
        "assume_user_role": _try(lambda: _assumed_store(BUCKET, user_role_arn) and None),
    }
    print(json.dumps(report, indent=2))
    return json.dumps(report)
```

```bash
REPO=~/Desktop/stargazerbio/stargazer
flyte_probe() { uv run --project "$REPO" --with 'boto3>=1.35,<2' python -c 'import sys; from flyte.cli.main import main; sys.argv[0] = "flyte"; main()' --config "$REPO/.flyte/union.yaml" "$@"; }
flyte_probe run --follow -p u-pryce -d development isolation_probe.py probe --subject 387300641116005877
flyte_probe run --follow -p flytesnacks -d development isolation_probe.py outsider --subject 387300641116005877 --user_role_arn arn:aws:iam::791359099513:role/stargazer-index-u-pryce
```

`flyte_probe` adds boto3 with `uv run --with`, because `flyte run` imports
the file locally and the venv's `flyte` script can't see `--with` packages
(measured for `dsql-asset-index`). Through it, `--help` resolves `probe`'s
`--subject` and `outsider`'s `--subject` and `--user_role_arn` (measured
2026-10-28; nothing was run).

**What to expect:**
- `probe` in `u-pryce`:
  - `whoami`: `AWS_ROLE_ARN` is the user's role, the token file exists with
    `aud` `sts.amazonaws.com`, and `caller` is
    `assumed-role/stargazer-index-u-pryce/…`. A missing token file means
    EKS's webhook skipped the container (see Current state); the run then
    fails before the report, and the pod's audit-log spec shows it.
  - `child_file` starts with
    `s3://stargazerbio-users/users/387300641116005877/flyte/raw/`.
  - `default_creds`: every `own_*` call and `child_file_get` succeed;
    `own_head_missing` is not found, or refused (then the `ListBucket`
    grant needs another shape); `other_*` and `root_list` are refused
    (`users/other/` holds nothing, so `other_get` is refused for want of
    `ListBucket` there, and `other_put` is the real test).
  - `tenant_bucket`: `list_own_runs` works (read), `put` is refused.
  - `shared_role`: the assume succeeds (it trusts every namespace), then
    `child_file_get` and `list_own` are refused.
- `outsider` in `flytesnacks`: `caller` is the shared role; `default_list`,
  `default_put` and `assume_user_role` are refused.

**5. Where the run data landed,** read-only: the `probe` run's inputs and
outputs under `users/387300641116005877/flyte/runs/`, nothing for it under
`metadata/v2/stargazerbio/u-pryce/development/`, and its outputs readable
through Union (`flyte get run`, and the console in the built-in browser).

**6. Revert the settings** right after: until Pieces 1–3 land, `u-pryce`'s
Stargazer store is still in the tenant bucket, where the user's role can
only read, so its real runs would fail. Set the project back to inheriting
all three, and confirm with `get settings`. Stop the dashboard Part A's
`upgrade` woke, and confirm no probe run is still going in either project.
The probe deletes the objects it wrote under `probe/`; the child's file
stays under `flyte/raw/` as run data, and the lifecycle rule expires its
noncurrent versions.

**Unverified**, settled by the runbook's own output:
- Whether the three project settings take effect, and on which writes
  (inputs are written when the run is created, outside the pod).
- Whether EKS's webhook version keeps our `AWS_ROLE_ARN` and still mounts
  the token.
- Whether Union's services need anything beyond `adminflyterole` to show
  outputs in the console.
- The bucket and role policies' refusals, and the missing-key `HeadObject`
  status.

**Measured locally (2026-10-28):** the probe's `_checks` against an
in-memory obstore store make every call as written (put, get, head,
list, a 12 MiB multipart put, delete), and `_whoami` runs with no AWS
environment.
