"""
### Factory for the per-notebook Knative AppEnvironment.

Called from `app/admin_app.py`'s `/launch` handler. Builds one
`flyte.app.AppEnvironment` per `(slug, mode)` pair, idempotent within a
user's Flyte project: clicking Edit twice on the same tile reuses the
existing Knative revision instead of creating a new one. The factory
bakes per-user secrets (GitHub OAuth token, fork owner, session secret)
into `env_vars` so the launch script can clone the user's fork into
`/workspace` and the reverse proxy can validate cookies.

Persistence model: the per-notebook pod owns its workspace as container-
local ephemeral storage. The launch script clones the user's fork into
`/workspace` on startup; the proxy's `/__sg__/workspace/sync` pushes
edits back to the fork; the SIGTERM hook fires the same sync before
Knative idles the pod. The fork is the source of truth; the pod is the
working copy. No PVC — Flyte v2 doesn't yet support `K8sPod` payloads
on app environments anyway.

The image (`stargazer-note`) does NOT install the stargazer Python
package at system level — every notebook declares its deps inline via
PEP 723 and marimo `--sandbox` provisions an isolated uv venv at boot.
System tools (BWA, samtools, GATK, conda) and the cookie-validating
reverse proxy ARE baked in.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os
from typing import Literal

import flyte
import flyte.app

from stargazer.config import STARGAZER_ENV_VARS


_NOTEBOOK_IMAGE = (
    f"{os.environ.get('STARGAZER_REGISTRY', 'localhost:30000')}/stargazer-note:latest"
)


def per_notebook_env(
    *,
    slug: str,
    mode: Literal["edit", "run"],
    notebook_path: str,
    fork_owner: str,
    github_token: str,
    session_secret: str,
) -> flyte.app.AppEnvironment:
    """Build a per-notebook AppEnvironment for one (slug, mode) launch.

    `notebook_path` is the absolute path inside the spawned pod — for
    image-baked notebooks that's `/stargazer/...`, for workspace notebooks
    it's `/workspace/...` (populated by the launch script's
    clone-on-startup against the user's fork).

    `fork_owner` + `github_token` let the launch script clone and the
    proxy's `/__sg__/workspace/sync` route commit + push. `session_secret`
    keys the proxy's cookie validation so authenticated browser sessions
    are accepted while drive-by requests get 401s.
    """
    return flyte.app.AppEnvironment(
        name=f"nb-{slug}-{mode}",
        description=f"Per-notebook app: {slug} ({mode})",
        image=_NOTEBOOK_IMAGE,
        args=[
            "/usr/local/bin/launch-notebook.sh",
            mode,
            notebook_path,
        ],
        port=8080,
        requires_auth=False,
        resources=flyte.Resources(memory=("2Gi", "6Gi")),
        env_vars={
            **STARGAZER_ENV_VARS,
            "FLYTE_DOMAIN": "development",
            "FORK_OWNER": fork_owner,
            "GITHUB_TOKEN": github_token,
            "SESSION_SECRET": session_secret,
        },
    )
