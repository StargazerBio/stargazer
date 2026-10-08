"""
### App-tier configuration — one home for the web tier's env-derived settings.

Mirrors `stargazer.config` (the SDK tier) for the deployment / web tier. Every
**non-secret** setting the app reads from the environment is resolved here once,
at import, with its default visible in one place — so the rest of `app/` reads
`config.FLYTE_DOMAIN` instead of sprinkling `os.environ.get(...)` with ad-hoc
defaults across modules.

What does **not** live here:

- **Secrets** (`PINATA_JWT`) — no committable default; baked into the App
  `env_vars` spec in `admin_app`.
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

# Default Flyte project/domain the admin pod targets for code-bundle uploads
# during per-user `serve.aio(...)` calls. The domain is also where every
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

# The one user this dashboard serves: their Union subject, baked in when the
# dashboard is deployed into their project. Unset admits nobody (fail closed).
# Notebook pods read the same variable for the same check (`app/proxy.py`).
OWNER_SUBJECT: str = os.environ.get("SG_OWNER_SUBJECT", "")
