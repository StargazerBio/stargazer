---
title: The hosted asset index moves to Aurora DSQL
status: next
priority: high
created: 2026-10-20
---

On Union each user's asset index is a SQLite file on their dashboard pod,
served to task and notebook pods over HTTP and kept durable by Litestream.
The index is only as available as that one pod, which scales to zero and is
redeployed on every release. Making it survive redeploys took a lease beside
the replica, a ~13 s pause in which index calls get 502s, and
`refuse_while_running`, and left a broken release able to take the dashboard
down (PR #52, closed unmerged). Instead, the hosted index moves to Aurora
DSQL, and the dashboard drops out of the index path.

Locally nothing changes: `SqliteIndex` and `~/.stargazer/index.db` stay. The
devbox gets a plain Postgres pod. Local-to-cluster promotion stays out of
scope. The work goes in three steps: the shared SQL index (ticket
`postgres-index`), the devbox's Postgres pod (ticket
`devbox-postgres-index`), then this ticket, Union.

## Why DSQL

Decided 2026-10-20, over DynamoDB and Aurora Serverless v2:

- **One SQL implementation.** DSQL supports `jsonb` columns and all of
  Postgres's JSON functions and operators (DSQL docs, supported data types),
  so the hosted index shares its SQL with `SqliteIndex`; the JSON accessor
  differs (`->>` for `json_extract`). DynamoDB would mean a second
  implementation of the five calls and of the filter semantics.
- **Leaving AWS needs no rewrite.** Code written for DSQL's subset of
  Postgres runs on any Postgres.
- **Queries run on the server and reads are strongly consistent,** so a
  `companion_of` lookup in `fetch()` returns only matching rows and always
  sees the upstream task's write. On DynamoDB that lookup would read the
  whole partition, or use a secondary index that is only eventually
  consistent.
- **Per-user isolation is enforced by the database** (below), as
  `dynamodb:LeadingKeys` would have been.
- **No cold start and $0 idle** (AWS knowledge card), where Aurora
  Serverless v2 resumes from auto-pause in seconds or bills ~$45/month at
  0.5 ACU.

Costs, from the DSQL docs:
- **Optimistic concurrency.** A conflicting write gets a serialization error
  (SQLSTATE 40001) instead of waiting, so every write retries.
- **Connections time out after 1 hour.** Long-lived pods reconnect.
- **Transaction limits:** one DDL statement per transaction, at most 3,000
  rows per transaction.
- **The devbox can't catch DSQL-only failures.** Plain Postgres accepts a
  superset of what DSQL does, so those surface only on the tenant. I know of
  no local DSQL emulator.

## Per-user isolation without Union

Union's documented route to a per-project role is for Union's team to bind
it to the namespace
([BYOC: enabling AWS resources](https://www.union.ai/docs/v2/union/deployment/byoc/enabling-aws-resources.md)).
This doesn't need that.

**Measured 2026-10-20** (read-only: `AWS_PROFILE=claude`, kubectl through
`stargazer-eks-access`):
- The cluster uses IRSA. Its OIDC provider is registered in IAM
  (`oidc.eks.us-west-2.amazonaws.com/id/21AC1CCD151FDBB6668C69B23D6ED9E1`),
  `pod-identity-webhook` is installed, and the EKS Pod Identity add-on
  isn't.
- In all six `u-*` namespaces the `default` service account is annotated
  with `union-us-west-2-stargazerbio-userflyterole`, including the
  namespaces `stargazer-users onboard` created for the test account. Union
  sets new namespaces up without a request per project.
- Task and app pods both run as `default` and get the projected token.
  Audit-log pod specs for task pod `ujgbbqc4xtlwgbb2hjst-a0-0` and pod
  `dashboard-00003` in `u-pryce-development` carry `AWS_ROLE_ARN`,
  `AWS_WEB_IDENTITY_TOKEN_FILE` and a mount at
  `/var/run/secrets/eks.amazonaws.com/serviceaccount`.
- `u-pryce-development`'s `default` can't create `serviceaccounts/token` or
  pods, read secrets, or patch service accounts, in its own namespace or in
  the test account's (`kubectl auth can-i`).
- The shared role trusts `system:serviceaccount:*:*`.

**The mechanism** (standard IRSA, not yet tried here):
- A pod's token is signed by the cluster, and its `sub` names the pod's
  namespace.
- A role whose trust policy requires
  `sub = system:serviceaccount:<project>-development:default` and
  `aud = sts.amazonaws.com` can be assumed with `AssumeRoleWithWebIdentity`
  only from that namespace.
- Pods keep the shared role as their default credentials. Only the index
  client assumes the per-user role, using the same token file.
- The shared role has never had DSQL access, so nothing has to be taken away
  from it. That's what makes this work without Union where storage
  isolation doesn't (ticket `per-user-storage-isolation`).

## Design

- One DSQL cluster for the org, single-region, us-west-2, created once by
  hand.
- One shared schema, `assets`, and one table per user in it,
  `assets.u_<handle>`, with `SqliteIndex`'s columns (keyvalues as `jsonb`).
  One database role per user, mapped to their IAM role with `AWS IAM
  GRANT`, holding `USAGE` on the schema and `SELECT`, `INSERT`, `UPDATE`,
  `DELETE` on its own table only. A database holds at most 1,000 tables;
  moving to one shared table later is a migration.
- `STARGAZER_INDEX_URL` picks the backend in `make_index`: a file path
  (SQLite, unchanged), a Postgres URL (devbox), or a DSQL endpoint with
  table and role (Union). The exact URL form is decided in the work.
- The dashboard's asset page uses the same index class as every other
  client.

## Pieces

- [ ] **Piece 0, the tenant check**, by hand, with the user's admin access
  (mine is read-only):
  - Create the cluster and the `assets` schema. For `u-pryce`, create the
    IAM role, the table, the database role and the grants.
  - From a task in `u-pryce-development`: assume the role from the token
    file, get a DSQL token, connect, upsert, and query by a keyvalue.
  - From a task in `flytesnacks`: `AssumeRoleWithWebIdentity` on
    `u-pryce`'s role is refused.
  - The shared role can't log in as `u-pryce`'s database role.
  - Confirm `INSERT … ON CONFLICT` and `->>` filters behave as in SQLite.
  - Time the assume, token and connect steps a task pays per call.
- [ ] **DSQL on `PostgresIndex`** (ticket `postgres-index`): connecting with
  a token from the assumed per-user role, retrying serialization errors, and
  reconnecting when a connection times out. `make_index` accepts the DSQL
  URL form.
- [ ] **Onboarding:**
  - `stargazer-users onboard` creates, on every call and safely when it
    already exists, the IAM role (trust as above, `dsql:DbConnect` on the
    cluster), then the user's table, role and grants as the DSQL admin.
  - This needs the admin's AWS credentials (`iam:CreateRole`,
    `iam:PutRolePolicy`, `dsql:DbConnectAdmin`). Today onboarding needs
    only Flyte credentials. `upgrade` needs no AWS access.
  - `offboard` deletes the IAM role and keeps the table, as it keeps the
    user's notebooks.
- [ ] **Deploys:** dashboards, notebook pods and the runs they start get
  the DSQL `STARGAZER_INDEX_URL`.
- [ ] **Migration:** each existing user's rows (the test account and
  `u-pryce`) are restored from their Litestream replica once and inserted.
- [ ] **Removals:**
  - Litestream: the image layer, and restore/replicate in
    `app/dashboard_launch.py`.
  - `app/index_api.py` and `HttpIndex`.
  - `refuse_while_running` and the retry loop in `upgrade`.
  - The PR #52 probe data under `stargazer-probe-revisions/` and
    `stargazer-probe-revisions-2/` in the bucket (about 300 objects; needs
    write access).
- [ ] **Docs:** the Asset Index section of `docs/architecture/app.md`,
  `configuration.md`, `app_internals.md`, `devbox_workarounds.md`,
  `contributing.md`'s devbox recipe.

**Verified when:**
- The germline workflow runs end to end on the test account.
- A dashboard redeploy while writes are going in costs no index call, since
  none reach the dashboard.
- A task in another project is refused on the user's table.

### Piece 0 runbook

For the user's admin profile (`pryce`), in zsh, from any directory outside
the repo. Every value that exists before the cluster is filled in, read
2026-10-21 with `AWS_PROFILE=claude` (read-only). It takes minutes, plus one
image build on the first `flyte run`.

The layout is one table per user in the shared `assets` schema (DSQL caps
a database at 10 schemas and 1,000 tables, and a cluster has one database).
`assets.u_other` stands in for a second user's table, so the probe can show
`u_pryce` is refused on it.

**Filled in, measured read-only:**
- Account `791359099513`. OIDC provider
  `arn:aws:iam::791359099513:oidc-provider/oidc.eks.us-west-2.amazonaws.com/id/21AC1CCD151FDBB6668C69B23D6ED9E1`:
  the account's only one (`aws iam list-open-id-connect-providers`), the
  issuer `aws eks describe-cluster` gives, client ID `sts.amazonaws.com`.
- Task pods in `u-pryce-development` run as service account `default`, with
  a projected token for audience `sts.amazonaws.com` at
  `/var/run/secrets/eks.amazonaws.com/serviceaccount/token`,
  `AWS_REGION=us-west-2` and `AWS_STS_REGIONAL_ENDPOINTS=regional` (EKS
  audit log: the `create` record of task pod `u2xmf4gdfvr4xltxqhnd-a0-0`,
  2026-10-21 01:07 UTC).
- The shared role gets implicitDeny for `dsql:DbConnect` and
  `dsql:DbConnectAdmin` (`aws iam simulate-principal-policy`).
- Not there yet: any DSQL cluster in us-west-2, the role
  `stargazer-index-u-pryce`, a DSQL service-linked role.
- `u-pryce` and `flytesnacks` both hold a `development` `EAGER_API_KEY`
  (Secrets Manager names), so pods start in both.
- `psql` isn't installed locally, so the runbook runs it in Docker.

**0. Shell.**

```bash
aws sso login --profile pryce
export AWS_PROFILE=pryce AWS_REGION=us-west-2
REPO=~/Desktop/projects/stargazer
ROLE=stargazer-index-u-pryce
ROLE_ARN=arn:aws:iam::791359099513:role/$ROLE
mkdir -p /tmp/dsql-probe && cd /tmp/dsql-probe
dsql_psql() { docker run --rm -i -e PGPASSWORD -e PGSSLMODE=require postgres:17-alpine psql -h "$DSQL_ENDPOINT" -d postgres -v ON_ERROR_STOP=1 "$@"; }
```

**1. The cluster:** single-region (no `--multi-region-properties`),
deletion protection on. Flags checked against the CLI reference and `aws
dsql help` (CLI 2.37.13).

```bash
CLUSTER_ID=$(aws dsql create-cluster --deletion-protection-enabled --tags Name=stargazer-index --query identifier --output text)
aws dsql wait cluster-active --identifier "$CLUSTER_ID"
DSQL_ENDPOINT=$(aws dsql get-cluster --identifier "$CLUSTER_ID" --query endpoint --output text)
CLUSTER_ARN=$(aws dsql get-cluster --identifier "$CLUSTER_ID" --query arn --output text)
echo "$CLUSTER_ID $DSQL_ENDPOINT $CLUSTER_ARN"
```

The endpoint is `<id>.dsql.us-west-2.on.aws`; set it by hand if
`get-cluster` prints `None`.

**2. The IAM role for `u-pryce`:** assumable only with a token whose `sub`
is `u-pryce-development`'s `default` service account and whose `aud` is
STS, allowed only `dsql:DbConnect` on this cluster.

```bash
cat > trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Federated": "arn:aws:iam::791359099513:oidc-provider/oidc.eks.us-west-2.amazonaws.com/id/21AC1CCD151FDBB6668C69B23D6ED9E1"},
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.us-west-2.amazonaws.com/id/21AC1CCD151FDBB6668C69B23D6ED9E1:sub": "system:serviceaccount:u-pryce-development:default",
          "oidc.eks.us-west-2.amazonaws.com/id/21AC1CCD151FDBB6668C69B23D6ED9E1:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF
cat > connect.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{"Effect": "Allow", "Action": "dsql:DbConnect", "Resource": "${CLUSTER_ARN}"}]
}
EOF
aws iam create-role --role-name "$ROLE" --assume-role-policy-document file://trust.json --description "Stargazer asset index: u-pryce's DSQL login" --query Role.Arn --output text
aws iam put-role-policy --role-name "$ROLE" --policy-name dsql-connect --policy-document file://connect.json
```

Both files were written by these heredocs in zsh and parsed as JSON
locally.

**3. Database objects, as the DSQL admin.** psql autocommits each
statement, so every DDL statement is its own transaction (DSQL allows one
per transaction). `u-pryce` becomes `u_pryce`, since an unquoted identifier
can't hold `-`. The schema is created once for every user; the table, role
and grants are per user.

```bash
export PGPASSWORD=$(aws dsql generate-db-connect-admin-auth-token --hostname "$DSQL_ENDPOINT" --region us-west-2 --expires-in 3600)
dsql_psql -U admin <<'EOF'
CREATE SCHEMA assets;
CREATE TABLE assets.u_pryce (cid TEXT PRIMARY KEY, uri TEXT NOT NULL, name TEXT NOT NULL, keyvalues JSONB NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE assets.u_other (cid TEXT PRIMARY KEY, uri TEXT NOT NULL, name TEXT NOT NULL, keyvalues JSONB NOT NULL, created_at TEXT NOT NULL);
CREATE ROLE u_pryce WITH LOGIN;
AWS IAM GRANT u_pryce TO 'arn:aws:iam::791359099513:role/stargazer-index-u-pryce';
GRANT USAGE ON SCHEMA assets TO u_pryce;
GRANT SELECT, INSERT, UPDATE, DELETE ON assets.u_pryce TO u_pryce;
SELECT pg_role_name, arn FROM sys.iam_pg_role_mappings;
SELECT tablename FROM pg_tables WHERE schemaname = 'assets' ORDER BY 1;
EOF
```

- The table is `SqliteIndex`'s, keyvalues as `JSONB` (DSQL stores `jsonb`
  up to 1 MiB a value and can't index it; `cid` is the key).
- `assets.u_other` gets no grant to `u_pryce`, which holds `USAGE` on the
  schema like every user will.
- Each statement follows DSQL's docs or the examples in awslabs' DSQL
  skill; none has run on DSQL yet. If one is refused, note it and go on.

Then check that the role mapping alone refuses an unmapped identity. The
admin holds `dsql:DbConnect` but isn't mapped to `u_pryce`, so expect a
refusal:

```bash
(export PGPASSWORD=$(aws dsql generate-db-connect-auth-token --hostname "$DSQL_ENDPOINT" --region us-west-2); dsql_psql -U u_pryce -c 'SELECT 1')
```

**4. The probe from task pods.** Save the block below as
`/tmp/dsql-probe/dsql_probe.py` (copy it, then `pbpaste > dsql_probe.py`).
Its image is Flyte's Debian base plus boto3, psycopg (`PostgresIndex`'s
driver) and certifi; Union's remote builder builds it on the first run.

```python
"""Piece 0 probe for ticket dsql-asset-index: per-user DSQL access from a task pod."""

import base64
import json
import os
import sqlite3
import time
from pathlib import Path

import boto3
import certifi
import flyte
import psycopg
from botocore.exceptions import ClientError

REGION = "us-west-2"
env = flyte.TaskEnvironment(
    name="dsql_probe",
    image=flyte.Image.from_debian_base(name="dsql-probe", platform=("linux/amd64",))
    .with_pip_packages("boto3>=1.35,<2", "psycopg[binary]>=3.2,<4", "certifi"),
    resources=flyte.Resources(cpu=1, memory="512Mi"),
)

# SqliteIndex's and PostgresIndex's SQL (src/stargazer/utils/index.py).
COLS = "cid, uri, name, keyvalues, created_at"
SCHEMA = ("CREATE TABLE IF NOT EXISTS {table} (cid TEXT PRIMARY KEY, uri TEXT NOT NULL, "
          "name TEXT NOT NULL, keyvalues {json} NOT NULL, created_at TEXT NOT NULL)")
UPSERT = (f"INSERT INTO {{table}} ({COLS}) VALUES (?, ?, ?, CAST(? AS {{json}}), ?) "
          "ON CONFLICT (cid) DO UPDATE SET uri = excluded.uri, name = excluded.name, "
          f"keyvalues = excluded.keyvalues RETURNING {COLS}")
MERGE = f"UPDATE {{table}} SET keyvalues = {{merge}} WHERE cid = ? RETURNING {COLS}"
QUERY = f"SELECT {COLS} FROM {{table}} WHERE {{kv}} = ? AND {{kv}} IN (?, ?)"
ENGINES = {
    "pg": {"json": "JSONB", "merge": "keyvalues || CAST(? AS JSONB)",
           "kv": "(keyvalues ->> CAST(? AS TEXT))"},
    "sqlite": {"json": "TEXT", "merge": "json_patch(keyvalues, ?)",
               "kv": "json_extract(keyvalues, ?)"},
}


def _row(r: tuple) -> dict:
    """A result row as a dict, keyvalues parsed (SQLite returns JSON text)."""
    kv = r[3] if isinstance(r[3], dict) else json.loads(r[3])
    return dict(zip(COLS.split(", "), [*r[:3], kv, r[4]], strict=True))


def _calls(run, engine: str, table: str) -> dict:
    """Insert, upsert on conflict, merge, query by keyvalue, delete: what each gave."""
    key = (lambda k: k) if engine == "pg" else (lambda k: f'$."{k}"')
    kv1 = json.dumps({"asset": "dsql_probe", "sample_id": "S1"})
    kv2 = json.dumps({"asset": "dsql_probe", "sample_id": "S2", "build": "GRCh38"})
    find = [key("asset"), "dsql_probe", key("sample_id")]
    steps = {
        "insert": (UPSERT, ["c1", "s3://b/1", "a.txt", kv1, "2026-01-01"]),
        "conflict": (UPSERT, ["c1", "s3://b/2", "b.txt", kv2, "2026-02-02"]),
        "merge": (MERGE, [json.dumps({"sample_id": "S3"}), "c1"]),
        "query_hit": (QUERY, [*find, "S3", "S9"]),
        "query_miss": (QUERY, [*find, "S1", "S9"]),
        "delete": ("DELETE FROM {table} WHERE cid = ?", ["c1"]),
        "after_delete": (f"SELECT {COLS} FROM {{table}} WHERE cid = ?", ["c1"]),
    }
    out = {}
    for name, (sql, params) in steps.items():
        cur = run(sql.format(**ENGINES[engine], table=table), params)
        out[name] = [_row(r) for r in cur.fetchall()] if cur.description else "done"
    return out


def _token(session, endpoint: str, admin: bool = False) -> str:
    """A DSQL auth token signed with the session's credentials (no AWS call)."""
    dsql = session.client("dsql", region_name=REGION)
    if admin:
        return dsql.generate_db_connect_admin_auth_token(endpoint, REGION)
    return dsql.generate_db_connect_auth_token(endpoint, REGION)


def _connect(endpoint: str, user: str, token: str, verify: bool = True):
    """An autocommit psycopg connection, PostgresIndex's driver."""
    ssl = {"sslmode": "require"}
    if verify:
        ssl = {"sslmode": "verify-full", "sslrootcert": certifi.where()}
        if psycopg.pq.version() >= 170000:
            ssl["sslnegotiation"] = "direct"
    return psycopg.connect(host=endpoint, port=5432, dbname="postgres", user=user,
                           password=token, connect_timeout=15, autocommit=True, **ssl)


def _try(fn) -> str:
    """'ok', or the error fn raised."""
    try:
        fn()
        return "ok"
    except (psycopg.Error, ClientError) as err:
        return f"{type(err).__name__} {getattr(err, 'sqlstate', None) or '-'}: {err}"


def _as_db_role(conn, db_role: str) -> dict:
    """What the database role can do on one connection, and the index SQL's results."""
    table = f"assets.{db_role}"
    out = {"whoami": conn.execute("SELECT current_user").fetchone()[0]}
    ddl = SCHEMA.format(json="JSONB", table=table)
    out["create_table_if_not_exists"] = _try(lambda: conn.execute(ddl))
    out["read_other_table"] = _try(lambda: conn.execute("SELECT count(*) FROM assets.u_other"))
    try:
        pg = _calls(lambda sql, p: conn.execute(sql.replace("?", "%s"), p), "pg", table)
    except psycopg.Error as err:
        pg = f"{type(err).__name__} {err.sqlstate}: {err}"
    lite = sqlite3.connect(":memory:")
    lite.execute(SCHEMA.format(json="TEXT", table="assets"))
    same = pg == _calls(lite.execute, "sqlite", "assets")
    return out | {"index_calls": pg, "same_as_sqlite": same}


@env.task
def probe(endpoint: str, role_arn: str, db_role: str = "u_pryce") -> str:
    """Assume the per-user role, log in as its database role, run the index SQL."""
    ns = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read_text()
    web_token = Path(os.environ["AWS_WEB_IDENTITY_TOKEN_FILE"]).read_text()
    claims = json.loads(base64.urlsafe_b64decode(web_token.split(".")[1] + "=="))
    report = {"namespace": ns, "sub": claims["sub"], "aud": claims["aud"]}
    shared = boto3.Session(region_name=REGION)  # the pod's default: the shared role
    report["shared_role_as_db_role"] = _try(
        lambda: _connect(endpoint, db_role, _token(shared, endpoint), False).close())
    sts = boto3.client("sts", region_name=REGION)
    report["timings_ms"], verify = [], True
    for _ in range(3):
        t0 = time.perf_counter()
        try:
            creds = sts.assume_role_with_web_identity(
                RoleArn=role_arn, RoleSessionName="dsql-probe", WebIdentityToken=web_token
            )["Credentials"]
        except ClientError as err:
            report["assume"] = f"refused: {err}"
            break
        t1 = time.perf_counter()
        user = boto3.Session(aws_access_key_id=creds["AccessKeyId"],
                             aws_secret_access_key=creds["SecretAccessKey"],
                             aws_session_token=creds["SessionToken"])
        token = _token(user, endpoint)
        t2 = time.perf_counter()
        try:
            conn = _connect(endpoint, db_role, token, verify)
        except psycopg.OperationalError as err:
            report["verify_full_error"], verify = str(err), False
            conn = _connect(endpoint, db_role, token, verify)
        t3 = time.perf_counter()
        conn.execute("SELECT 1").fetchone()
        t4 = time.perf_counter()
        conn.close()
        ms = [round((b - a) * 1000) for a, b in [(t0, t1), (t1, t2), (t2, t3), (t3, t4)]]
        report["timings_ms"].append(dict(zip(["assume", "token", "connect", "select_1"], ms)))
    else:
        report["assume"] = "ok"
        report["tls"] = "verify-full" if verify else "require"
        with _connect(endpoint, db_role, token, verify) as conn:
            report |= _as_db_role(conn, db_role)
        report["user_role_as_admin"] = _try(
            lambda: _connect(endpoint, "admin", _token(user, endpoint, True), False).close())
    print(json.dumps(report, indent=2))
    return json.dumps(report)
```

```bash
flyte_probe() { uv run --project "$REPO" --with 'boto3>=1.35,<2' --with certifi python -c 'import sys; from flyte.cli.main import main; sys.argv[0] = "flyte"; main()' --config "$REPO/.flyte/union.yaml" "$@"; }
flyte_probe run --follow -p u-pryce -d development dsql_probe.py probe --endpoint "$DSQL_ENDPOINT" --role_arn "$ROLE_ARN"
flyte_probe run --follow -p flytesnacks -d development dsql_probe.py probe --endpoint "$DSQL_ENDPOINT" --role_arn "$ROLE_ARN"
flyte_probe get run --in-phase running -p u-pryce -d development
flyte_probe get run --in-phase running -p flytesnacks -d development
```

`flyte run` imports the file locally, and the repo's venv has no boto3 or
certifi. `flyte_probe` adds them with `uv run --with` and calls the CLI from
Python, because the venv's `flyte` script can't see `--with` packages
(measured: `ModuleNotFoundError: No module named 'boto3'`). Through it,
`--help` resolves the task's `--endpoint`, `--role_arn` and `--db_role`
(measured; nothing was run). The last two commands confirm both runs ended.

Each run prints a JSON report and returns it as its output. What to expect:
- Both: `sub` is `system:serviceaccount:<project>-development:default`,
  `aud` is `sts.amazonaws.com`, and `shared_role_as_db_role` is refused (the
  shared role has no `dsql:DbConnect`).
- `flytesnacks`: `assume` is refused (`AccessDenied`) and the report stops.
- `u-pryce`: `assume: ok`, then:
  - `timings_ms`, three rounds: `assume` (the STS call), `token` (a DSQL
    client plus local signing), `connect` (TLS and IAM auth), `select_1`.
  - `tls`: `verify-full` against certifi's bundle, which carries Amazon Root
    CA 1, or `require` with `verify_full_error`.
  - `whoami`: `u_pryce`.
  - `create_table_if_not_exists`: Postgres 16 refuses it with `42501
    permission denied for schema assets` although the table exists. If DSQL
    does too, `PostgresIndex`'s constructor can't run as a user's role, so
    on DSQL it skips the DDL and onboarding creates the table.
  - `read_other_table`: `42501 permission denied for table u_other`.
  - `same_as_sqlite: true`: the insert, the `ON CONFLICT` update (keeping
    `created_at`), the `||` merge, a `->>` hit and miss, and the delete
    return what SQLite returns. `false`, or an error in `index_calls`, most
    likely means `RETURNING`, which DSQL's supported-SQL page doesn't list.
  - `user_role_as_admin`: refused (no `dsql:DbConnectAdmin`).

The Postgres 16 values above were measured locally on 2026-10-21
(`postgres:16-alpine`): step 3's SQL without the `AWS IAM` and `sys` lines,
then the probe's `_as_db_role` as `u_pryce`, then the teardown below.

Then drop the stand-in second user's table:

```bash
dsql_psql -U admin -c 'DROP TABLE assets.u_other;'
```

**5. Record** under `## Piece 0 results (<date>)`, then tick Piece 0:
- The cluster ID, ARN and endpoint, and the time to `ACTIVE`.
- Step 3: any refused statement, the mapping row, the table list, and the
  unmapped login's refusal.
- Both probe reports verbatim, with their run names.
- Decisions for Piece 1: from the timings, whether the client caches the
  assumed credentials (1 h) and the token (15 min by default, a week at
  most) per process and reuses connections. DSQL accepts 100 new
  connections a second per cluster (1,000 burst) and ends each after an
  hour.

**Teardown, to undo it.** After `assets.u_other` is gone. Order measured on
Postgres 16: `DROP ROLE` fails while the role still holds `USAGE` on the
schema.

```bash
export PGPASSWORD=$(aws dsql generate-db-connect-admin-auth-token --hostname "$DSQL_ENDPOINT" --region us-west-2 --expires-in 3600)
dsql_psql -U admin <<'EOF'
AWS IAM REVOKE u_pryce FROM 'arn:aws:iam::791359099513:role/stargazer-index-u-pryce';
DROP TABLE assets.u_pryce;
REVOKE USAGE ON SCHEMA assets FROM u_pryce;
DROP ROLE u_pryce;
DROP SCHEMA assets;
EOF
aws iam delete-role-policy --role-name "$ROLE" --policy-name dsql-connect
aws iam delete-role --role-name "$ROLE"
```

Keep the cluster: the rest of this ticket uses it, and idle it bills only
storage. To delete it anyway:

```bash
aws dsql update-cluster --identifier "$CLUSTER_ID" --no-deletion-protection-enabled
aws dsql delete-cluster --identifier "$CLUSTER_ID"
aws dsql wait cluster-not-exists --identifier "$CLUSTER_ID"
```

**Unverified**, because nothing here could run against DSQL; the runbook's
own output settles each:
- On DSQL: all of step 3's SQL, and in particular table-level `GRANT` (the
  docs describe permissions as schema-level grants), `RETURNING`, `CREATE
  TABLE IF NOT EXISTS` without `CREATE`, `DROP SCHEMA` and `DROP ROLE`.
- From the pod: `verify-full` with certifi's bundle and
  `sslnegotiation=direct`. From Docker: psql 17's TLS to DSQL.
- The refusal messages, and whether the remote builder builds the probe
  image as written.

## Meanwhile

`main` still has the bug PR #52 fixed. A redeploy runs the old and new
dashboard pods side by side, and both replicate to the same path (measured
2026-10-19, test account, throwaway root):
- The old pod rewrote L0 transaction 2 a minute after the new pod had
  uploaded its own, with no request reaching it.
- Both pods compacted the same files, with overlapping ranges.
- A write the old pod accepted was missing after a fresh restore.

`App.deactivate(wait=True)` returns while the pods take another 30–50 s to
exit. Until this ticket lands, stop a dashboard and wait about 90 s before
redeploying it (`onboard` re-runs and `upgrade`).
