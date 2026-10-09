"""
### Per-notebook image + AppEnvironment factory.

Defines the shared `notebook-app` programmatic `flyte.Image` used by
every per-notebook Knative pod, and `per_notebook_env(...)` — the
AppEnvironment factory the dashboard's `/launch` handler invokes.

The image layers, on top of the Flyte debian base:

- `micromamba` plus the bioinformatics tools (gatk4, samtools, bwa,
  bwa-mem2) — system-level so subprocess calls from inside the
  per-notebook sandbox venv can reach them.
- `uv` — needed by `marimo --sandbox` to provision each notebook's
  PEP 723 venv at boot.
- `claude` (Claude Code CLI) — the AI agent, on PATH for the dropdown
  terminal the proxy injects. Pinned standalone binary (auto-update off);
  auth is interactive (`claude` browser login) and ephemeral.
- `marimo` plus the reverse proxy's web deps (`fastapi`,
  `uvicorn`, `httpx`, `websockets`). The proxy's storage calls use the
  `flyte` SDK the base image already carries.
- `app/proxy.py` baked at `/usr/local/lib/sg_proxy.py` (top-level module,
  importable via `PYTHONPATH=/usr/local/lib` as `sg_proxy:asgi_app`; not
  under `app/` so it doesn't get shadowed by Flyte's loaded_modules
  code bundle which lands `app/` into the pod's `/home/flyte` cwd).
- `app/terminal_overlay.html` baked at `/usr/local/lib/terminal_overlay.html`,
  the dropdown-terminal markup the proxy reads relative to its own `__file__`
  and injects into marimo's HTML responses.
- `app/launch-notebook.sh` baked at `/usr/local/bin/launch-notebook.sh`,
  invoked by the AppEnvironment `args=[...]`.

Stargazer itself is NOT installed at the system level — every notebook
declares its deps inline via PEP 723 and the sandbox venv resolves them
at boot, including `stargazer` via `[tool.uv.sources]`.

Persistence model: the workspace store (`app.workspace_store`) is the
source of truth and the pod is a working copy. At launch the script hydrates
the owner's notebooks into `WORKSPACE_NOTEBOOK_DIR` and their own snapshots
into `SNAPSHOT_NOTEBOOK_DIR`, both flat (`<dir>/<slug>.py`). The proxy writes
edited notebooks back on a short interval and once more when the pod scales
to zero. No PVC: pod-local disk plus the object store is cheaper and faster.

Auth: pods run `requires_auth=True`, so access control is the platform's alone;
`SG_OWNER_SUBJECT` only keys the pod's workspace store. No credential of any
kind is baked into the pod env.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os
from datetime import timedelta
from typing import Literal

import flyte
import flyte.app
from flyte._initialize import get_client, get_init_config
from flyte.remote import App
from flyteidl2.app import app_payload_pb2
from flyteidl2.common import identifier_pb2, list_pb2

from app import config
from app.notebook_meta import NotebookResources
from stargazer.config import IMAGE_PLATFORM, PROJECT_ROOT, STARGAZER_ENV_VARS

# Bake the proxy as a TOP-LEVEL module (not under `app/`) because Flyte's
# loaded_modules code bundle ships an `app/` package into the pod's cwd
# (`/home/flyte`) at every per-notebook deploy. If the baked-in proxy lived at
# `/usr/local/lib/app/proxy.py`, that cwd-shadowed `app` package would mask
# it and `uvicorn app.proxy:asgi_app` would fail to import.
_PROXY_LIB_DIR = "/usr/local/lib"
_PROXY_MODULE = "sg_proxy"
_LAUNCH_BIN = "/usr/local/bin"

# Where a launch hydrates the owner's notebooks, flat as `<dir>/<slug>.py`. The
# dashboard builds `notebook_path` from these; the proxy mirrors them.
WORKSPACE_NOTEBOOK_DIR = "/workspace"
SNAPSHOT_NOTEBOOK_DIR = "/snapshots"


# Layered build recipe. Consumed only by the deployer's build step
# (`onboard.build_notebook_image`), which bakes the built, content-hashed URI
# into each dashboard as `STARGAZER_NOTEBOOK_IMAGE`. A dashboard never resolves
# this recipe itself: it has no Docker daemon or project layout, and the hash
# its Python state would compute could differ from the deployer's. A unique URI
# per deploy also means nodes can never serve a stale cached image.
notebook_app_img_recipe = (
    flyte.Image.from_debian_base(
        name="notebook-app",
        registry=os.environ.get("STARGAZER_REGISTRY"),
        platform=IMAGE_PLATFORM,
    )
    .with_apt_packages("ca-certificates", "curl", "git", "bzip2")
    .with_commands(
        [
            # micromamba + bioinformatics tools (same recipe as gatk_env).
            # Reachable by subprocess from inside each notebook's sandbox venv.
            "curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest "
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
            # Claude Code CLI — the AI agent, on PATH inside the dropdown
            # terminal. The native installer is a standalone arch-detecting
            # binary (no node). Install under a fixed build HOME so its launcher
            # (~/.local/bin/claude) and versioned binaries (~/.local/share/claude)
            # land at stable absolute paths independent of the `flyte` runtime
            # user's HOME, make the tree world-readable, then symlink onto PATH.
            # Pinned to a stable version for repro (auto-update disabled via the
            # image env below); auth is interactive (`claude` browser login) and
            # ephemeral per the pod's storage.
            "mkdir -p /opt/claude-cli "
            "&& curl -fsSL https://claude.ai/install.sh | HOME=/opt/claude-cli bash -s 2.1.153 "
            "&& chmod -R a+rX /opt/claude-cli "
            "&& ln -s /opt/claude-cli/.local/bin/claude /usr/local/bin/claude",
        ]
    )
    .with_pip_packages(
        # Launcher marimo, pinned. Notebooks don't list marimo in their PEP 723
        # headers — `marimo --sandbox` injects *this* version into each kernel
        # venv, so launcher and kernel are the same build by construction.
        "marimo==0.23.6",
        "fastapi>=0.115",
        "uvicorn>=0.34",
        "httpx>=0.27",
        "websockets>=12",
    )
    # `/usr/local/lib/` already exists in the base image, so the COPY drops
    # `proxy.py` into it without needing a directory-creating trailing-slash.
    # Renamed to `sg_proxy.py` in the next command to avoid clashing with
    # Flyte's `app/` code bundle and to keep the module name unambiguous.
    .with_source_file(PROJECT_ROOT / "app" / "proxy.py", _PROXY_LIB_DIR)
    # Static dropdown-terminal markup the proxy reads at import (relative to its
    # own __file__) and injects into marimo's HTML. Baked into the same dir as
    # the proxy so that relative read resolves in-pod.
    .with_source_file(PROJECT_ROOT / "app" / "terminal_overlay.html", _PROXY_LIB_DIR)
    .with_source_file(PROJECT_ROOT / "app" / "launch-notebook.sh", _LAUNCH_BIN)
    # Bake the stargazer source tree at `/stargazer/` so each notebook's
    # `[tool.uv.sources] stargazer = { path = "/stargazer", editable = true }`
    # resolves inside the marimo --sandbox venv. Image-shipped notebooks live
    # under `/stargazer/src/stargazer/notebooks/{tutorials,workflows}/`.
    .with_source_file(PROJECT_ROOT / "pyproject.toml", "/stargazer/")
    .with_source_file(PROJECT_ROOT / "README.md", "/stargazer/")
    .with_source_folder(PROJECT_ROOT / "src", "/stargazer/src")
    .with_source_folder(PROJECT_ROOT / "app", "/stargazer/app")
    .with_commands(
        [
            f"mv {_PROXY_LIB_DIR}/proxy.py {_PROXY_LIB_DIR}/{_PROXY_MODULE}.py",
            f"chmod +x {_LAUNCH_BIN}/launch-notebook.sh",
            # Pre-create the hydration targets owned by the flyte runtime
            # user so the launch script can write into them at startup.
            f"mkdir -p {WORKSPACE_NOTEBOOK_DIR} {SNAPSHOT_NOTEBOOK_DIR} "
            f"&& chown -R flyte:flyte {WORKSPACE_NOTEBOOK_DIR} {SNAPSHOT_NOTEBOOK_DIR}",
        ]
    )
    # PYTHONPATH lets the proxy import as `sg_proxy`. DISABLE_AUTOUPDATER pins
    # Claude Code to the baked version: the install tree is read-only for the
    # flyte user, so a background self-update would otherwise re-download into
    # ephemeral home on every cold-start, defeating the pin and bloating storage.
    .with_env_vars({"PYTHONPATH": _PROXY_LIB_DIR, "DISABLE_AUTOUPDATER": "1"})
)


def per_notebook_env(
    *,
    slug: str,
    mode: Literal["edit", "run"],
    notebook_path: str,
    owner_subject: str,
    admin_url: str,
    index_url: str,
    resources: NotebookResources | None = None,
) -> flyte.app.AppEnvironment:
    """Build a per-notebook AppEnvironment for one (slug, mode) launch.

    `notebook_path` is the absolute path inside the spawned pod: image-baked
    notebooks live under `/stargazer/...`, the owner's notebooks under
    `WORKSPACE_NOTEBOOK_DIR` and their own snapshots under
    `SNAPSHOT_NOTEBOOK_DIR`, both hydrated by the launch script.

    `owner_subject` is the owner's platform user id. The pod sits behind the
    platform login (`requires_auth=True`), which is its only access control.
    `SG_OWNER_SUBJECT` keys where the pod hydrates from and saves to in the
    workspace store
    (`STARGAZER_WORKSPACE_ROOT`). `admin_url` is the admin app's public base
    URL, which the proxy's `/__sg__/dashboard` route redirects to.
    `index_url` is the dashboard's in-cluster address, where the pod and the
    runs it starts index their assets (`STARGAZER_INDEX_URL`); the assets
    themselves go under the workspace root (`STARGAZER_STORE_ROOT`). No
    credential is baked into the env: notebook code can read it.

    `resources` is the notebook's declared `[tool.stargazer]` spec, honored
    as-authored (no ceiling). When None — image-baked tutorials and workflows
    notebooks — the env falls back to the legacy `("2Gi", "6Gi")`
    request/limit, which the memory-heavy scRNA notebook depends on.
    """
    if not config.NOTEBOOK_IMAGE:
        raise RuntimeError(
            "STARGAZER_NOTEBOOK_IMAGE is unset: deploy with `stargazer-users`, "
            "which builds the notebook image and bakes its URI in."
        )
    flyte_resources = (
        flyte.Resources(cpu=resources.cpu, memory=resources.memory)
        if resources is not None
        else flyte.Resources(memory=("2Gi", "6Gi"))
    )
    return flyte.app.AppEnvironment(
        name=f"nb-{slug}-{mode}",
        description=f"Per-notebook app: {slug} ({mode})",
        # `from_base` marks the URI as prebuilt, so serving skips any build or
        # existence check and just hands the URI to Flyte.
        image=flyte.Image.from_base(config.NOTEBOOK_IMAGE),
        # `exec` is load-bearing, not cosmetic. Flyte's `fserve` (PID 1) runs
        # these args via `Popen(" ".join(args), shell=True)` and, on the Knative
        # SIGTERM at scale-to-zero, forwards the signal to that single direct
        # child only. Without `exec`, Debian's `/bin/sh -c "launch-notebook.sh …"`
        # can linger as an intermediate shell that swallows SIGTERM, so the
        # launch script's final `exec uvicorn` never receives it and the proxy's
        # shutdown flush (the final save of workspace edits) is silently skipped.
        # Prepending `exec` forces the `sh -c` wrapper to replace itself with the
        # script, which then `exec`s uvicorn into that same direct-child slot —
        # so the proxy is the process `fserve` signals. See launch-notebook.sh.
        args=[
            "exec",
            f"{_LAUNCH_BIN}/launch-notebook.sh",
            mode,
            notebook_path,
        ],
        port=8080,
        requires_auth=True,
        resources=flyte_resources,
        scaling=flyte.app.Scaling(
            replicas=(0, 1), scaledown_after=timedelta(minutes=30)
        ),
        # Notebook-named URL (`{slug}-{mode}-{hash}`) instead of the default.
        domain=flyte.app.Domain(
            subdomain=flyte.app.Subdomain.from_app_name(f"{slug}-{mode}")
        ),
        env_vars={
            **STARGAZER_ENV_VARS,
            "FLYTE_DOMAIN": config.FLYTE_DOMAIN,
            "SG_OWNER_SUBJECT": owner_subject,
            "STARGAZER_WORKSPACE_ROOT": config.WORKSPACE_ROOT,
            "STARGAZER_ADMIN_URL": admin_url,
            "STARGAZER_INDEX_URL": index_url,
            **(
                {"STARGAZER_STORE_ROOT": config.WORKSPACE_ROOT}
                if config.WORKSPACE_ROOT
                else {}
            ),
        },
    )


async def list_project_apps(project: str, domain: str, limit: int = 500) -> list[App]:
    """List every App deployment in `project`, regardless of name or state.

    `flyte.remote.App.listall` only honors the ambient init-config project, so
    we issue the project-scoped list against the same client the SDK uses —
    there's no public list API that takes a project. The dashboard passes its
    own project; onboarding passes the user's when stopping their apps. Callers re-`App.get` by name for
    authoritative status, since a list payload may not carry full conditions.

    Used by `/workspace/cleanup` to find stopped apps for notebooks no longer on
    the dashboard (e.g. deleted ones), which a name-bounded probe would miss.
    """
    cfg = get_init_config()
    project_id = identifier_pb2.ProjectIdentifier(
        organization=cfg.org, name=project, domain=domain
    )
    apps: list[App] = []
    token = None
    while len(apps) < limit:
        resp = await get_client().app_service.list(
            request=app_payload_pb2.ListRequest(
                request=list_pb2.ListRequest(limit=100, token=token),
                org=cfg.org,
                project=project_id,
            )
        )
        apps.extend(App(a) for a in resp.apps)
        token = resp.token
        if not token:
            break
    return apps
