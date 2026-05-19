"""
### Per-user notebook AppEnvironment.

A single `flyte.app.AppEnvironment` running `marimo edit` against the
bundled scRNA tutorial notebook. The admin landing app deploys one
instance of this env per user by calling
`flyte.with_servecontext(project=<user_project>, domain=...).serve.aio(notebook_env)`.
Per-user isolation comes from Flyte's per-project storage / cache split,
not from varying the env definition.

The image is the pre-built `stargazer-note:latest` produced by the `note`
target in the project `Dockerfile` — the admin deploy entrypoint
(`app.admin_app:main`) builds and pushes it before `flyte.serve(app_env)`.
Referenced by string (not `flyte.Image.from_*`) so Flyte does not attempt
to (re)build it inside the admin pod, which lacks a Docker daemon and the
project source layout.

Devbox note: `requires_auth=False` because devbox does not enforce app
auth. In production this should be `True`, gated by the user's identity.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os

import flyte
import flyte.app

from stargazer.config import STARGAZER_ENV_VARS


_NOTEBOOK_IMAGE = f"{os.environ['STARGAZER_REGISTRY']}/stargazer-note:latest"

# Path inside the stargazer-note image (Dockerfile sets WORKDIR /stargazer).
_NOTEBOOK_PATH_IN_IMAGE = "src/stargazer/notebooks/tutorials/scrna_tutorial.py"


notebook_env = flyte.app.AppEnvironment(
    name="notebook",
    description="Per-user marimo notebook (scRNA tutorial)",
    image=_NOTEBOOK_IMAGE,
    args=[
        "marimo",
        "edit",
        _NOTEBOOK_PATH_IN_IMAGE,
        "--port",
        "8080",
        "--host",
        "0.0.0.0",
        "--headless",
        "--no-token",
    ],
    port=8080,
    requires_auth=False,
    resources=flyte.Resources(memory=("2Gi", "6Gi")),
    env_vars=STARGAZER_ENV_VARS,
)
