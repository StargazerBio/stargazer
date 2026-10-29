---
title: per-user-storage-isolation
status: review
priority: high
created: 2026-10-05
pr: 14
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
  Flyte settings point the files Flyte uploads into their prefix.

No Union step is needed. The shared role stays, and any pod can still
assume it, but nothing in the user bucket is in its reach.

**Not covered:**
- **Run metadata.** Inputs, outputs and errors (`.pb`) stay in Union's
  bucket under `metadata/v2/stargazerbio/<project>/`, readable by every pod
  through the shared role. Union's output API reads them only from its own
  bucket, even when `run.run_base_dir` names another (measured, Piece 0).
  For Stargazer they hold asset metadata, store URIs and small values; the
  files move. Moving them waits on Union fixing that read, which the user
  raises with them.
- **The image repository.** Every pod can push to the ECR repository
  other users' tasks run from: the shared role always could, and the
  user's role has to, since Union builds images from a task pod in the
  user's project.

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
  `notebooks/`, `settings.json`) and the files Flyte uploads
  (`flyte/raw/`).
- **Its bucket policy** grants each role tagged `stargazer-subject` object
  read, write and delete under `users/<that subject>/`, and `ListBucket` on
  that prefix only, so no per-user policy names the bucket. It denies the
  shared role outright, denies non-TLS requests, and allows Union's
  services (`adminflyterole`) the `users/*/flyte/` prefixes, which run
  metadata needs once Union reads it from there. Union's roles themselves
  are untouched.
- **One IAM role per user,** `stargazer-user-<project>`, replacing
  `stargazer-index-<project>`, tagged `stargazer-subject=<subject>` and
  `stargazer-project=<project>`, with:
  - `dsql-connect`: their index table, as today.
  - `stargazer-user-union-read`, a managed policy shared by every user's
    role: read on Union's three buckets (code bundles and anything else
    Flyte reads there), write to the run metadata prefix its project tag
    names, and ECR pull and push for image builds.
  - Anything per-user later becomes another policy on it.
- **All of it is code:** the bucket, its policy and the managed policy in
  infra's tofu stack (`aws/storage.tf`), each user's role, tag and
  attachment in onboarding.
- **Each user's project settings:** `storage.raw_data_path` points at
  their `flyte/raw/` prefix, and `environment_variables` sets
  `AWS_ROLE_ARN` to their role and `AWS_WEB_IDENTITY_TOKEN_FILE` to the
  token path, for every task pod. `run.run_base_dir` stays unset.
- **App pods** (dashboard, notebooks) get the same two variables from
  their deploys, since the project setting reaches task pods only.
- **Stargazer's code doesn't change:** its calls use the pod's default
  credentials, which are now the user's role. Its deploys point
  `STARGAZER_STORE_ROOT` and `STARGAZER_WORKSPACE_ROOT` at the bucket.

## Pieces

- [x] **Piece 0, the tenant check.** Part A by the user's admin profile
  (my AWS access is read-only), Part B by me. Runbook and results below.
- [ ] **Piece 1, infra** (one PR, branch `feat/per-user-storage-isolation`):
  - [x] `aws/storage.tf`: the bucket, its policy and
    `stargazer-user-union-read` (commit `d2688dc`; plan below).
  - [x] Onboarding tags the role with the user's subject and attaches
    `stargazer-user-union-read`; offboarding detaches it before deleting
    the role (commit `d2688dc`).
  - [x] The managed policy's ECR pull and push (`5bf9000`), and its write
    to the project's run metadata prefix by the `stargazer-project` tag,
    which onboarding sets (`21c172a`).
  - [x] `tenant.env`'s `STARGAZER_WORKSPACE_ROOT` becomes
    `s3://stargazerbio-users` (`ea786a4`).
  - [x] Onboarding makes `stargazer-user-<project>` in place of
    `stargazer-index-<project>` (`app.deploy.iam_role_name`). The
    role-making code moves out of `stargazer_users.user_index` into a
    module of its own, since it's no longer the index's. A new role
    already gets its DSQL login mapped afresh (`ea786a4`:
    `stargazer_users/user_role.py`).
  - [x] Onboarding applies the project's two settings (`ea786a4`).
  - [x] Deploys: dashboards and notebook pods get `AWS_ROLE_ARN` and
    `AWS_WEB_IDENTITY_TOKEN_FILE`. The index URL's `role_arn` is the same
    ARN (`ea786a4`).
  - [x] The rename for `u-pryce`: re-onboarded with `upgrade`, which made
    `stargazer-user-u-pryce`.
  - [x] Delete `stargazer-index-u-pryce` with onboarding's `_remove_role`
    (user's admin profile; `GetRole` gives `NoSuchEntity`, 2026-10-29). Its DSQL mapping stays: DSQL never honours a
    mapping for a deleted role.
- [x] **Piece 2, Stargazer docs** (stargazer PR 104): `configuration.md` (where
  hosted files and run data live), `runtime.md`'s pod contract (pods run
  as the user's role), `runtime_internals.md`.
- [ ] **Piece 3, migration** (after Piece 1 deploys):
  - [x] Copy the test account's `assets/` and `uploads/` to
    `s3://stargazerbio-users/users/387300641116005877/` and rewrite its index
    rows' `uri` prefix `s3://union-us-west-2-stargazerbio/stargazer/` →
    `s3://stargazerbio-users/`: a task in `u-pryce`, as the user's own role
    (results below). Its workspace prefix was empty; the old `notebooks/`,
    `settings.json`, `index/` and `index-lease/` are leftovers of earlier
    layouts and weren't copied.
  - [x] Delete the old `stargazer/users/` prefix (the user, 2026-10-29;
    `stargazer/` in Union's bucket lists 0 objects).
    Past runs' data in `metadata/v2/stargazerbio/u-pryce/` stays where it
    is.
  - [x] [alpha-notice](alpha-notice.md): the notice's wording stays. Run
    records are still readable by every pod, and infra's `app.md` now gives
    that as its reason.

**Verified when**, on the test account:
- The germline workflow runs end to end, started from a notebook, with its
  files under the user's prefix and its run metadata only under the
  project's prefix in Union's bucket.
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
3. **Pods default to the user's role,** so the files Flyte uploads and
   Stargazer's files are both private without any code knowing about
   roles. Private is the default; sharing takes a deliberate write with the
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
8. **Run metadata stays in Union's bucket for now.** Union's output API
   reads it only from there, so moving it breaks the CLI, the console and
   image builds. The user's role writes only its own project's prefix
   there, by tag; the shared role already reads all of it, so the grant
   exposes nothing new.

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
branch, so `stargazer-index-u-pryce` gets its tags and the managed policy.
It calls the step on its own, without `upgrade`'s dashboard redeploy.

```bash
cd ~/Desktop/stargazerbio/infra/.claude/worktrees/per-user-storage-isolation
AWS_PROFILE=pryce uv run -q --env-file tenant.env python -c "from stargazer_users.user_index import ensure_user_index; ensure_user_index('u-pryce', '387300641116005877')"
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

**5. Where the run data landed,** read-only: the child's file under
`users/387300641116005877/flyte/raw/`, the run's `.pb` files under
`metadata/v2/stargazerbio/u-pryce/development/<run>/`, and its outputs
readable through Union (the SDK's `Run.outputs()` and action details, and
the console in the built-in browser).

**6. Revert the settings** right after: until Pieces 1–3 land, `u-pryce`'s
Stargazer store is still in the tenant bucket, where the user's role can
only read, so its real runs would fail. Set the project back to inheriting
both, with a settings file of `{}`, and confirm with `get settings`. Stop the dashboard Part A's
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

## Piece 0 results (2026-10-29)

Part A applied by the user from infra's `feat/per-user-storage-isolation`
(`d2688dc`, then `5bf9000`), state copied back to the main checkout. Read
back with `AWS_PROFILE=claude`: the bucket with versioning and all six
policy statements (the per-user grant renders as
`users/${aws:PrincipalTag/stargazer-subject}/*`), and
`stargazer-index-u-pryce` tagged `stargazer-subject=387300641116005877`
with `stargazer-user-union-read` attached.

**Measured:**
- **`flyte edit settings --from-file`** applies a file as the scope's whole
  override set: a file of `{}` removes all three overrides and the project
  inherits again.
- **The role override reaches task pods.** Union's image build for the
  probe runs as a task in `u-pryce`, and with the settings on it ran as the
  user's role: its push to ECR failed with `401 Unauthorized` (build run
  `uwlw7bsk6dhbskhbrgqb`). The shared role pushes through Union's
  `imagebuilder` policy. With the same ECR actions on
  `stargazer-user-union-read` (`5bf9000`), the next build passed
  (`upj56brzwt8g9xt9d5hd`, 7 s).
- **Writes follow `run.run_base_dir` into our bucket.** Both builds'
  `inputs.pb`, `outputs.pb` and `error.pb` landed under
  `s3://stargazerbio-users/users/387300641116005877/flyte/runs/stargazerbio/u-pryce/development/<run>/…`,
  written by Union's services (through `UnionServicesRunData`) and by the
  pod; nothing for them in the tenant bucket.
- **Union's reads don't.** Fetching the passed build's outputs failed:
  `failed to get outputs: … object
  's3://union-us-west-2-stargazerbio/users/387300641116005877/flyte/runs/stargazerbio/u-pryce/development/upj56brzwt8g9xt9d5hd/a0/0/outputs.pb'
  not found`. Union's output API keeps its own bucket and takes only the
  key from the run's location. So with `run.run_base_dir` in another
  bucket, nothing that reads outputs through Union works: the CLI, the
  console, and `flyte run`'s own image build step. The probe task never
  started.

**With the split** (`21c172a` applied, role tags
`stargazer-subject=387300641116005877` and `stargazer-project=u-pryce`
read back; settings `storage.raw_data_path` and the two variables only):

- **`probe` in `u-pryce` succeeded** (run `u9z4bwv8t7wbqvlh5wvk`; the
  CLI's log stream dropped with `Request was cancelled`, so the report
  comes from `flyte get logs`):
  - `whoami`: `AWS_ROLE_ARN` is the user's role, the token file exists at
    the variable's path, `sub` `system:serviceaccount:u-pryce-development:default`,
    `aud` `sts.amazonaws.com`, `AWS_REGION` and `AWS_STS_REGIONAL_ENDPOINTS`
    set, `caller`
    `arn:aws:sts::791359099513:assumed-role/stargazer-index-u-pryce/…`. So
    EKS's webhook keeps a preset `AWS_ROLE_ARN` and still mounts the token.
  - `child_file`:
    `s3://stargazerbio-users/users/387300641116005877/flyte/raw/g2/stargazerbio/u-pryce/development/u9z4bwv8t7wbqvlh5wvk/…/child.txt`.
  - `default_creds`: `own_put`, `own_get` (`hello`), `own_head` (`5`),
    `own_list`, `own_multipart_12MiB`, `own_multipart_size` (`12582912`),
    `own_delete` and `child_file_get` succeed; `own_head_missing` is a
    `404`, so `StorageClient.upload`'s exists check works as it is;
    `other_get`, `other_put`, `other_list` and `root_list` are `403`.
  - `tenant_bucket`: `list_own_runs` reads 381 keys; `put` outside the
    project's metadata prefix is `403`.
  - `shared_role`, assumed with the pod's token: `child_file_get` and
    `list_own` are `403`.
- **`outsider` in `flytesnacks` succeeded** (run `u4ddw6gdwq45dcx2mz84`):
  its pod runs as the shared role; listing and writing the user's prefix
  are `403`, and `AssumeRoleWithWebIdentity` on the user's role is
  `AccessDenied`.
- **Where it landed:** the run's `outputs.pb` and the child's `inputs.pb`
  and `outputs.pb` under
  `metadata/v2/stargazerbio/u-pryce/development/u9z4bwv8t7wbqvlh5wvk/` in
  Union's bucket, written by the pods as the user's role; the child's file
  is the run's only object in ours. The probe's own test objects were
  deleted by the probe.
- **Through Union:** the SDK reads the run's outputs and the child's
  `File` reference; the console (signed in as the test account in the
  built-in browser) shows the child's input and its file output. The
  console links a file to the AWS S3 console rather than downloading it
  through Union, so a file in our bucket costs nothing there.

Earlier attempts left `flyte/runs/` objects for runs
`uwlw7bsk6dhbskhbrgqb`, `upj56brzwt8g9xt9d5hd` and `iJLTp5zfKXJ_jnXpQhho`
under the test account's prefix; they're harmless and go with the
account's data.

**Remaining risk found on the way:** the user's role can push to ECR, as
the shared role already lets every pod do, so any user can push to the
image repository other users' tasks run from. Not new, but run data being
private doesn't cover it.

Teardown: settings reverted on `u-pryce` (`get settings` shows all three
empty), the dashboard the `upgrade` woke is stopped, and no runs are going
in `u-pryce` or `flytesnacks`. The `upgrade` hung after its deploy: Knative had
the revision ready at 07:01 UTC while Union's app status stayed
`ASSIGNED`, so `deploy_dashboard`'s serve watch, which has no timeout,
never returned.

## Verification recipe: Each user's files behind their own role

A user's dashboard, notebook pods and runs read and write their files in
`s3://stargazerbio-users/users/<subject>/`, as their own IAM role, and
nothing else of anyone's.

### Sub-features
- **R1** The dashboard, notebook pods and task pods run as
  `stargazer-user-<project>`, with the token mounted.
- **R2** The dashboard's explorer lists the user's assets, downloads one,
  and stores an upload under the new bucket.
- **R3** A notebook's workspace saves to `users/<subject>/workspace/` in the
  new bucket and comes back after the pod restarts.
- **R4** A task in the user's project finds an asset the dashboard stored,
  fetches it, and stores a new one under the new bucket.
- **R5** Other projects and the shared role are refused on the user's
  prefix (Piece 0's probe and `outsider`).

### How to get to it (user POV)
The test account's dashboard, `https://u-pryce.apps.stargazerbio.us-west-2.unionai.cloud`:
the asset explorer, and a workspace notebook launched from it.

### Driving it
Preconditions: infra's `feat/per-user-storage-isolation` applied (tofu) and
`./stargazer-users upgrade --email pryce@stargazer.bio` run from it; the
built-in browser signed in to the console as the test account.

1. R1: `kubectl get pods -n u-pryce-development -o yaml` (read-only) on the
   dashboard, a notebook pod and a task pod shows `AWS_ROLE_ARN` =
   `arn:aws:iam::791359099513:role/stargazer-user-u-pryce` and the
   `aws-iam-token` mount.
2. R2: in the explorer, the migrated assets list; one downloads; a small
   upload appears, and `aws s3 ls s3://stargazerbio-users/users/387300641116005877/`
   (`AWS_PROFILE=claude`) shows its object.
3. R3: launch a workspace notebook, write a file, wait for a save, then
   list `users/387300641116005877/workspace/`; stop the app, launch again,
   and the file is there.
4. R4: a task in `u-pryce` with `STARGAZER_INDEX_URL`, `STARGAZER_STORE_ROOT`
   and `STARGAZER_OWNER` as a notebook forwards them `query()`s the
   upload, `download()`s it and `upload()`s a derived file; its row's `uri`
   is under the new bucket and the file is there.
5. Teardown: stop every app started, no live runs in `u-pryce`.

## Verification results (2026-10-29)

Infra's `feat/per-user-storage-isolation` at `ea786a4`, applied (tofu: no
changes beyond `21c172a`) and `upgrade --email pryce@stargazer.bio` run by
the user. All measured unless labelled.

- **R1:** `stargazer-user-u-pryce` exists, tagged
  `stargazer-subject=387300641116005877` and `stargazer-project=u-pryce`,
  with `dsql-connect` and `stargazer-user-union-read`. `u-pryce`'s settings
  hold `storage.raw_data_path` and the two variables. The dashboard pod and
  the notebook pod carry `AWS_ROLE_ARN` =
  `arn:aws:iam::791359099513:role/stargazer-user-u-pryce`, the token path,
  `STARGAZER_STORE_ROOT` and `STARGAZER_WORKSPACE_ROOT` =
  `s3://stargazerbio-users`, and the `aws-iam-token` mount (`kubectl get
  pod -o jsonpath`, read-only). Task pods: every run below reports
  `assumed-role/stargazer-user-u-pryce` from STS. The `upgrade` didn't hang
  this time.
- **Migration** (run `up2wqwdt6qvnhk7pmx5k`, image from Flyte's Debian base
  plus `stargazer-bio==2026.10.28`; the release image's `flyte` rejected the
  client's `--user-log-level` flag, run `ug2qjsbwh4lpp8fh8xbk`): caller
  `assumed-role/stargazer-user-u-pryce`, 80 objects copied (6,063,016,447
  bytes), 80 rows on the old root before, 0 after, 80 on the new root, none
  missing its file.
- **R2** (the dashboard, `2026.10.28-ea786a4`, driven from the built-in
  browser as the test account): `/assets/list?source=mine` returns 80 rows,
  all under `s3://stargazerbio-users/`. `/assets/download/<cid>?network=private`
  of `demo_cohort.csv` returns 200, 61 bytes, SHA-256 `7e045fc6…a0cc`, the
  same as the object read straight from the bucket. A 62-byte upload
  through `/assets/tus` (201, then 204) is indexed at
  `s3://stargazerbio-users/users/387300641116005877/uploads/fa7a1ccc…/isolation-r2.txt`
  with `_owner` stamped, and the object is there and not in the old prefix.
- **R3:** a new workspace notebook `isocheck`, saved by the dashboard to
  `users/387300641116005877/workspace/isocheck.py`, launched in edit mode;
  its pod logged `[sg] hydrated 1 file(s)`. A cell wrote
  `/workspace/r3-isolation.txt` and reported its caller as
  `assumed-role/stargazer-user-u-pryce`; within 30 s both files were in the
  new bucket's `workspace/` and nothing in the old one. After `/stop` and a
  new `/launch`, the new pod logged `[sg] hydrated 2 file(s)`.
- **R4** (run `u86bl6f7jwm2klsjtcjd`, with the env a notebook forwards):
  the task `query()`d the R2 upload at its new `uri`, `download()`ed its
  text, and `upload()`ed a derived `verify_note` at
  `s3://stargazerbio-users/users/387300641116005877/assets/bafkreicj2f645h…/isolation-r4.txt`
  with `_owner` and `source` in its keyvalues; the object holds the
  derived text.
- **R5** from the notebook cell: the shared role, assumed with the pod's
  token, gets `AccessDenied` on `ListObjectsV2` of the user's prefix, and
  the user's role gets `AccessDenied` on `users/other/`. From task pods:
  Piece 0's `probe` and `outsider`.

- **Germline end to end** (the devbox tier's `seed` and `check` with the
  storage settings a notebook forwards, run from SDK code with
  `STARGAZER_API_KEY_SECRET=UNION_API_KEY`): seed
  [`udnvtwxhzd74857ktvb6`](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/u-pryce/runs/udnvtwxhzd74857ktvb6),
  `germline_short_variant_discovery`
  [`ujq7pwb7j5x4z5vmzcc2`](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/u-pryce/runs/ujq7pwb7j5x4z5vmzcc2),
  check
  [`ucjtbngb5g6kg4g2rslf`](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/u-pryce/runs/ucjtbngb5g6kg4g2rslf).
  The cohort VCF (`joint_call_gvcfs`, `cohort-554f1b1b`, from `NA12829` on
  `GRCh38`) is at
  `s3://stargazerbio-users/users/387300641116005877/assets/bafkreifmhune…/cohort-554f1b1b_genotyped.vcf`;
  another pod found it with `assemble()` and read sample `NA12829`, 47
  records on `chr17:7658421-7697490`, as the devbox test expects. Every
  step's output (index, BAMs, metrics, GVCF) landed under the user's prefix
  in the new bucket, and `stargazer/` in Union's bucket stayed empty. The
  GATK image built and pushed as the user's role.

Teardown: `isocheck` stopped and deleted, `union_dashboard.py teardown`
stopped the dashboard (`live runs: []`), no runs in `flytesnacks`.
