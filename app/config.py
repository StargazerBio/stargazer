"""
### App-tier configuration — one home for the web tier's env-derived settings.

Mirrors `stargazer.config` (the SDK tier) for the deployment / web tier. Every
**non-secret** setting the app reads from the environment is resolved here once,
at import, with its default visible in one place — so the rest of `app/` reads
`config.SECURE_COOKIES` instead of sprinkling `os.environ.get(...)` with ad-hoc
defaults across modules.

What does **not** live here:

- **Secrets** (`SESSION_SECRET`, `GITHUB_CLIENT_SECRET`, `GITHUB_APP_PRIVATE_KEY`)
  — they have no committable default and are assembled into the App `env_vars`
  spec in `admin_app` (see the secret-baking block there).
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

_TRUTHY = ("1", "true", "yes", "on")


def _flag(name: str, default: bool = False) -> bool:
    """Parse an env var as a boolean flag (`1/true/yes/on`, case-insensitive).

    Unset (or empty) returns `default`; any other value is parsed.
    """
    raw = os.environ.get(name, "").strip().lower()
    return raw in _TRUTHY if raw else default


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

# Auth cookies get the `Secure` attribute (HTTPS-only). Defaults on for union
# (TLS) and off for devbox, which serves plain HTTP — a Secure cookie is never
# sent there, so local login would silently fail. `STARGAZER_SECURE_COOKIES`
# overrides either way. The proxy mirrors this (via the value baked into each
# notebook pod's env) so all cookie writers agree.
SECURE_COOKIES: bool = _flag("STARGAZER_SECURE_COOKIES", default=TARGET == "union")

# The notebook-app image every per-notebook pod runs, as the exact URI built at
# deploy time (`admin_app.main` bakes it into the admin pod's env). Unset in a
# bare local `uvicorn` run, where launching a notebook then errors clearly.
NOTEBOOK_IMAGE: str | None = os.environ.get("STARGAZER_NOTEBOOK_IMAGE") or None

# The GitHub App's public URL handle (e.g. `stargazer-workspaces`), used to build
# the install-redirect URL at `/workspace/enable`. Unset → installs aren't wired
# up, so enable lands straight on the dashboard. Non-secret.
GITHUB_APP_SLUG: str | None = os.environ.get("GITHUB_APP_SLUG") or None

# The admin app's public base URL (e.g. `https://admin.stargazer.bio`). Used to
# build OAuth callback URIs and the per-notebook `admin_url`. Unset → fall back
# to the request's own base_url (so local `uvicorn --reload` needs no config).
LANDING_BASE_URL: str | None = os.environ.get("LANDING_BASE_URL") or None

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
