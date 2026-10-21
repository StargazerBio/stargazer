"""
### App-tier configuration — one home for the web tier's env-derived settings.

Mirrors `stargazer.config` (the SDK tier) for the deployment / web tier. Every
**non-secret** setting the app reads from the environment is resolved here once,
at import, with its default visible in one place — so the rest of `app/` reads
`config.FLYTE_DOMAIN` instead of sprinkling `os.environ.get(...)` with ad-hoc
defaults across modules.

What does **not** live here:

- **Secrets.** A dashboard's or notebook pod's owner can read its app spec,
  so nothing secret is baked into one. Both get the Pinata key as a Flyte
  secret instead (`admin_app`, `per_notebook`).
- **The per-notebook proxy** (`app/proxy.py`) — it's baked into the notebook
  image as a *standalone* module with no `app` package on its path, so it can't
  import this; it re-reads the few env vars it needs (mirroring the values here).

Values are read at import: in a deployed pod the environment is baked before the
process starts, so import-time == runtime. Tests that need a specific value
`monkeypatch.setattr` the constant here rather than poking the environment.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os

from stargazer.config import PROJECT_ROOT

# Which backend this deploy aims at: `devbox` (local cluster) or `union` (the
# hosted tenant). Validated and defaulted by `stargazer.config`, which also
# forwards it into every pod. The settings below take their defaults from it.
TARGET: str = os.environ["STARGAZER_TARGET"]

# The deployer's Flyte config file. Both live under the gitignored `.flyte/`:
# `config.yaml` points at the devbox, `union.yaml` at the hosted tenant (remote
# image builder). Only the deployer shell reads it; pods init in-cluster.
FLYTE_CONFIG = (
    PROJECT_ROOT / ".flyte" / ("union.yaml" if TARGET == "union" else "config.yaml")
)

# The notebook-app image every per-notebook pod runs, as the exact URI built at
# deploy time (`app.onboard` bakes it into each dashboard's env). Unset in a
# bare local `uvicorn` run, where launching a notebook then errors clearly.
NOTEBOOK_IMAGE: str | None = os.environ.get("STARGAZER_NOTEBOOK_IMAGE") or None

# The Flyte project/domain the dashboard pod targets for code-bundle uploads
# during per-notebook `serve.aio(...)` calls. The domain is also where every
# per-notebook app is served and looked up — `production` for a prod deploy.
FLYTE_PROJECT: str = os.environ.get("FLYTE_PROJECT", "flytesnacks")
FLYTE_DOMAIN: str = os.environ.get("FLYTE_DOMAIN", "development")

# Root URI of the workspace store (`app.workspace_store`): every user's
# notebooks live under `<root>/users/<subject>/`. On Union this is a prefix in
# the tenant bucket, e.g. `s3://union-us-west-2-stargazerbio/stargazer`. Unset
# means workspace saving isn't configured for this deploy.
WORKSPACE_ROOT: str = os.environ.get("STARGAZER_WORKSPACE_ROOT", "")


def stand_in_subject(env) -> str:
    """`SG_STAND_IN_SUBJECT`, except on Union, where it's never honored."""
    if env.get("STARGAZER_TARGET") == "union":
        return ""
    return env.get("SG_STAND_IN_SUBJECT", "")


# A subject for requests that arrive with no identity, for a deploy with no
# login in front of it (`app.identity`). Union's login always forwards one.
STAND_IN_SUBJECT: str = stand_in_subject(os.environ)

# Whether the dashboard offers public assets: the Public tab, browsing the
# public network and uploading to it. On by default, wherever the org's Pinata
# key is; a deploy turns it off with `STARGAZER_PUBLIC_ASSETS=off`, which
# onboarding passes on to each dashboard. Tasks and notebooks aren't affected.
PUBLIC_ASSETS: bool = os.environ.get("STARGAZER_PUBLIC_ASSETS", "on") != "off"

# The commit this dashboard was deployed from (`app.onboard.release_version`),
# shown on its page for debugging. Unset in a bare local run, which shows none.
VERSION: str = os.environ.get("STARGAZER_VERSION", "")

# The one user this dashboard serves: their Union subject, baked in when the
# dashboard is deployed into their project. It keys their state whoever
# visits; unset (a local run), the visitor's own subject does
# (`app.identity.current_user`). Notebook pods read the same variable to key
# where they load and save notebooks (`app/proxy.py`).
OWNER_SUBJECT: str = os.environ.get("SG_OWNER_SUBJECT", "")


def auth_issuer(env) -> str:
    """Who signs the tokens Union's login forwards: Union's sign-in service on
    Union, nobody elsewhere."""
    if env.get("STARGAZER_TARGET") == "union":
        return "https://signin.us-west-2.unionai.cloud"
    return ""


# On Union every request has to carry a token this issuer signed
# (`app.identity`): an app's in-cluster address skips the login and passes on
# whatever headers a pod sends, so the plain identity headers prove nothing.
# Empty where there's no login in front (the devbox, a local run), and the
# headers are taken as they come.
AUTH_ISSUER: str = auth_issuer(os.environ)


def admin_subjects(env) -> frozenset[str]:
    """`STARGAZER_ADMIN_SUBJECTS`, a comma-separated list of Union subjects."""
    raw = env.get("STARGAZER_ADMIN_SUBJECTS", "")
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


# Who besides the owner may open this dashboard and its notebooks on Union: org
# admins, set by the deployer (`app.onboard` bakes it). Union's own check,
# that the visitor can view the project, never runs on the in-cluster address.
ADMIN_SUBJECTS: frozenset[str] = admin_subjects(os.environ)


def console_url(env) -> str:
    """The Union console's address on Union, nothing elsewhere.

    Union gives every app pod the tenant's host as `_U_EP_OVERRIDE` (bare;
    the SDK's `dns:///<host>` form is accepted too), and the console is
    served from that host, which also names the org. The devbox's endpoint
    is an in-cluster address with no console users can reach, so off Union
    this is empty.
    """
    if env.get("STARGAZER_TARGET") != "union":
        return ""
    host = env.get("_U_EP_OVERRIDE", "").removeprefix("dns:///")
    return f"https://{host}" if host else ""


# Where the dashboard links its owner to see their runs. Empty means no link.
CONSOLE_URL: str = console_url(os.environ)
