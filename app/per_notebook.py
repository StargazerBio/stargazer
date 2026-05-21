"""
### Per-notebook image + AppEnvironment factory.

Defines the shared `notebook-app` programmatic `flyte.Image` used by
every per-notebook Knative pod, and `per_notebook_env(...)` — the
AppEnvironment factory the admin app's `/launch` handler invokes.

The image layers, on top of the Flyte debian base:

- `micromamba` plus the bioinformatics tools (gatk4, samtools, bwa,
  bwa-mem2) — system-level so subprocess calls from inside the
  per-notebook sandbox venv can reach them.
- `uv` — needed by `marimo --sandbox` to provision each notebook's
  PEP 723 venv at boot.
- `marimo` plus the cookie-validating reverse proxy's web deps
  (`fastapi`, `uvicorn`, `itsdangerous`, `httpx`, `websockets`).
- `app/proxy.py` baked at `/usr/local/lib/app/proxy.py` (importable via
  `PYTHONPATH=/usr/local/lib` as `app.proxy:asgi_app`).
- `app/launch-notebook.sh` baked at `/usr/local/bin/launch-notebook.sh`,
  invoked by the AppEnvironment `args=[...]`.

Stargazer itself is NOT installed at the system level — every notebook
declares its deps inline via PEP 723 and the sandbox venv resolves them
at boot, including `stargazer` via `[tool.uv.sources]`.

Persistence model: the per-notebook pod owns its workspace as container-
local ephemeral storage. The launch script clones the user's fork into
`/workspace` on startup; the proxy's `/__sg__/workspace/sync` pushes
edits back to the fork; the SIGTERM hook fires the same sync before
Knative idles the pod. The fork is the source of truth; the pod is the
working copy. No PVC — Flyte v2 doesn't yet support `K8sPod` payloads
on app environments anyway.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os
from typing import Literal

import flyte
import flyte.app

from stargazer.config import PROJECT_ROOT, STARGAZER_ENV_VARS


_PROXY_LIB_DIR = "/usr/local/lib/app"
_LAUNCH_BIN = "/usr/local/bin"


notebook_app_img = (
    flyte.Image.from_debian_base(
        name="notebook-app",
        registry=os.environ["STARGAZER_REGISTRY"],
        platform=("linux/amd64", "linux/arm64"),
    )
    .with_apt_packages("ca-certificates", "curl", "git", "bzip2")
    .with_commands(
        [
            # micromamba + bioinformatics tools (same recipe as gatk_env).
            # Reachable by subprocess from inside each notebook's sandbox venv.
            'arch=$(uname -m); case "$arch" in x86_64) marc=linux-64;; '
            "aarch64|arm64) marc=linux-aarch64;; esac; "
            "curl -Ls https://micro.mamba.pm/api/micromamba/${marc}/latest "
            "| tar -xj -C /usr/local/bin --strip-components=1 bin/micromamba",
            "/usr/local/bin/micromamba create -p /opt/conda -y "
            "-c bioconda -c conda-forge gatk4 samtools bwa bwa-mem2 "
            "&& /usr/local/bin/micromamba clean -a -y",
            "ln -s /opt/conda/bin/gatk /usr/local/bin/gatk "
            "&& ln -s /opt/conda/bin/java /usr/local/bin/java "
            "&& ln -s /opt/conda/bin/samtools /usr/local/bin/samtools "
            "&& ln -s /opt/conda/bin/bwa /usr/local/bin/bwa "
            "&& ln -s /opt/conda/bin/bwa-mem2 /usr/local/bin/bwa-mem2",
            # uv — used by `marimo --sandbox` to build per-notebook venvs.
            "curl -LsSf https://astral.sh/uv/install.sh | sh "
            "&& install -m 755 /root/.local/bin/uv /usr/local/bin/uv "
            "&& install -m 755 /root/.local/bin/uvx /usr/local/bin/uvx",
        ]
    )
    .with_pip_packages(
        "marimo>=0.10.0",
        "fastapi>=0.115",
        "uvicorn>=0.34",
        "itsdangerous>=2.1",
        "httpx>=0.27",
        "websockets>=12",
    )
    .with_source_file(PROJECT_ROOT / "app" / "proxy.py", _PROXY_LIB_DIR)
    .with_source_file(PROJECT_ROOT / "app" / "launch-notebook.sh", _LAUNCH_BIN)
    .with_commands(
        [
            f"touch {_PROXY_LIB_DIR}/__init__.py",
            f"chmod +x {_LAUNCH_BIN}/launch-notebook.sh",
        ]
    )
    .with_env_vars({"PYTHONPATH": "/usr/local/lib"})
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
        image=notebook_app_img,
        args=[
            f"{_LAUNCH_BIN}/launch-notebook.sh",
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
