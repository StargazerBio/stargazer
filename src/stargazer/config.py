"""
### Centralized configuration for Stargazer.

Sets environment variable defaults at import time. Consumers read
os.environ directly rather than importing named values from this module.

Also what every task environment shares: the platform its image is built
for, the variables and secrets forwarded into its pods, and the image
recipes: a domain's tasks build from its `env.py`'s header
(`task_image()`), and a notebook's own tasks from the notebook's header
(`notebook_image()`).
The environments themselves live in their domains' `env.py`
(`stargazer.tasks.scrna.env`, `stargazer.tasks.gatk.env`).

`init_flyte()` is the one Flyte init for notebooks, the MCP server and the
tests: an in-cluster client in a hosted notebook pod, the config file anywhere
else.

Rules:
- PINATA_JWT: No default — absence means no public tier (Pinata) at all.
- PINATA_GATEWAY: IPFS gateway for public downloads. Defaults to the project's
  dedicated Pinata gateway.
- STARGAZER_LOCAL: Scratch space for task outputs and the download cache.
  Defaults to ~/.stargazer/local.
- STARGAZER_STORE_ROOT: Where asset bytes are stored — a local directory or a
  bucket URI (e.g. `s3://stargazerbio-users`). Defaults
  to ~/.stargazer/store.
- STARGAZER_INDEX_URL: The asset index — a SQLite file path, a
  `postgresql://` URL (the devbox's), or a `dsql://` URL naming a user's
  table on Aurora DSQL (Union's). Defaults to ~/.stargazer/index.db.
- STARGAZER_OWNER: The Union subject that owns new assets (their folder in
  the store, and `_owner`). Unset locally.
- STARGAZER_API_KEY_SECRET: The Flyte secret holding the project's API key.
  When it's set, every environment declares that secret, as the variable
  Flyte's in-cluster client reads its key from, so a pod can call the cluster
  as its project. Union needs one; a cluster without a login (the devbox), or
  a local run, leaves it unset. Forwarded into every pod.

Where images are pushed is Flyte's own setting, `FLYTE_IMAGE_REGISTRY`. Flyte
fixes an image's registry when the image is defined, so the environments here
take it at import, not from the config a later init reads.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import contextlib
import hashlib
import inspect
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import flyte
from loguru import logger as logger  # noqa: PLC0414

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The account's dedicated gateway, since public ones rate-limit full
# downloads. Every download through it, signed in or not, counts against the
# account's bandwidth.
os.environ.setdefault(
    "PINATA_GATEWAY", "https://maroon-written-fowl-769.mypinata.cloud"
)
os.environ.setdefault("STARGAZER_LOCAL", str(Path.home() / ".stargazer" / "local"))

# Storage locations set explicitly (a deploy, a pod's env) are forwarded into
# task pods; the local defaults below are not, since a pod can't use them.
_STORAGE_KEYS = ("STARGAZER_STORE_ROOT", "STARGAZER_INDEX_URL")
_EXPLICIT_STORAGE = {k: os.environ[k] for k in _STORAGE_KEYS if os.environ.get(k)}
os.environ.setdefault("STARGAZER_STORE_ROOT", str(Path.home() / ".stargazer" / "store"))
os.environ.setdefault(
    "STARGAZER_INDEX_URL", str(Path.home() / ".stargazer" / "index.db")
)

# Every Stargazer image is built for x86_64 only, the architecture Union runs.
# GATK's GenomicsDB ships an x86_64-only native library, so an arm64 build
# can't joint-call; on an Apple-silicon devbox these pods run emulated.
IMAGE_PLATFORM = ("linux/amd64",)

_log_dir = Path.home() / ".stargazer" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
logger.remove()
logger.add(_log_dir / "stargazer.log", rotation="10 MB", retention=5)
logger.add(sys.stderr, level="INFO")


def _stargazer_env_vars() -> dict[str, str]:
    """env_vars forwarded into task pods via the TaskEnvironments.

    The spec serializes from the submitting process. STARGAZER_OWNER rides
    along when set (hosted workspaces), so a pod stores outputs in the
    owner's folder and stamps their ``_owner``; without it a pod writes as
    ``local``. PINATA_GATEWAY and STARGAZER_API_KEY_SECRET ride along so a
    pod resolves them like the submitter.
    STARGAZER_STORE_ROOT and STARGAZER_INDEX_URL ride along only when set
    explicitly: a pod can't use the local store or index.
    """
    env = {
        "PINATA_GATEWAY": os.environ["PINATA_GATEWAY"],
        **_EXPLICIT_STORAGE,
    }
    key_secret = os.environ.get("STARGAZER_API_KEY_SECRET")
    if key_secret:
        env["STARGAZER_API_KEY_SECRET"] = key_secret
    owner = os.environ.get("STARGAZER_OWNER")
    if owner:
        env["STARGAZER_OWNER"] = owner
    return env


STARGAZER_ENV_VARS = _stargazer_env_vars()

STARGAZER_SECRETS = [flyte.Secret(key="PINATA_JWT", as_env_var="PINATA_JWT")]

# The project's own API key, stored as a secret in the project. Union gives
# pods no key of its own, and without one a pod's client can't call Union: a
# workflow can't start its child tasks, and a notebook can't run them. Flyte's
# in-cluster client reads the key from this variable.
if os.environ.get("STARGAZER_API_KEY_SECRET"):
    STARGAZER_SECRETS.append(
        flyte.Secret(
            key=os.environ["STARGAZER_API_KEY_SECRET"],
            as_env_var="_UNION_EAGER_API_KEY",
        )
    )


def log_execution() -> str:
    """Start a per-execution log sink and return the execution ID.

    Derives the workflow name from the calling function, fetches the current
    git commit hash, and creates a dedicated logfile for this execution.
    Warns if the git tree has uncommitted changes.
    """
    workflow = inspect.currentframe().f_back.f_code.co_name
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,  # missing/!git dir falls back to "unknown"
        )
        commit = result.stdout.strip() or "unknown"

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,  # non-repo is tolerated, not fatal
        )
        if status.stdout.strip():
            commit += "-dirty"
            logger.warning("Git tree is dirty — uncommitted changes present")
    except FileNotFoundError:
        commit = "unknown"

    execution_id = f"{workflow}-{commit}-{timestamp}"
    logger.add(_log_dir / f"{execution_id}.log")

    public = "on" if os.environ.get("PINATA_JWT") else "off"
    logger.info(
        f"Execution started: {execution_id} "
        f"| store={os.environ['STARGAZER_STORE_ROOT']} "
        f"| index={os.environ['STARGAZER_INDEX_URL']} "
        f"| public tier={public} "
        f"| gateway={os.environ['PINATA_GATEWAY']} "
        f"| local_dir={os.environ['STARGAZER_LOCAL']}"
    )
    return execution_id


def _bundle_root() -> Path:
    """Where a hosted run's code bundle comes from.

    A checkout's runs carry its source, from the directory holding the
    `stargazer` package (the MCP server's, editable from the image's
    `/stargazer`). A notebook's environment installs the SDK as a package,
    whose tasks a task pod imports from its own image, the same release, so
    its runs carry only the running notebook's folder (marimo sets
    `__main__.__file__` to the notebook), where its own tasks are. Not
    site-packages: Flyte never bundles a file there, and refuses an empty
    bundle, and an environment links the package's files from the uv cache,
    which Flyte's bundler resolves on one side of a comparison and not the
    other.
    """
    if _checkout():
        return Path(__file__).resolve().parents[1]
    notebook = getattr(sys.modules["__main__"], "__file__", None)
    return Path(notebook).parent if notebook else Path.cwd()


def init_flyte() -> None:
    """Initialize Flyte wherever Stargazer runs.

    A hosted notebook pod (`_U_EP_OVERRIDE` set) has no config file, but it
    carries the endpoint, an API key and the owner's org, project and domain,
    which make an in-cluster client for the owner's project. Its runs bundle
    code from `_bundle_root()`. Anywhere else the config file decides, as
    `flyte.init_from_config()` does: with none, runs stay in the caller's own
    process.
    """
    if not os.environ.get("_U_EP_OVERRIDE"):
        flyte.init_from_config()
        return
    # `init_in_cluster` takes the code bundle's root from the cwd and has no
    # parameter for it.
    with contextlib.chdir(_bundle_root()):
        flyte.init_in_cluster(
            org=os.environ.get("FLYTE_ORG"),
            project=os.environ.get("FLYTE_PROJECT"),
            domain=os.environ.get("FLYTE_DOMAIN"),
        )


def _with_source(image: flyte.Image) -> flyte.Image:
    """`image` with the checkout's stargazer installed on top, from its source.

    A layer of its own, so a source change rebuilds only it; the checkout's
    .dockerignore keeps docs, tests, git history and pixi's environments out
    of it, and out of every other folder the image copies. It's named here
    because Flyte otherwise reads the one in `flyte.init`'s root, which is the
    cwd, or `src/` in a notebook pod (`init_flyte`). A task pod resolves the
    tasks it calls as installed modules (`stargazer.tasks…`), so the package
    must be the checkout's, wherever the run was submitted from. uv installs
    into the pixi environment, which the layer below made `VIRTUAL_ENV`, with
    any core dependency the checkout has gained since the release the layer
    below installed.
    """
    return (
        image.with_dockerignore(PROJECT_ROOT / ".dockerignore")
        .with_source_folder(PROJECT_ROOT, "/opt/stargazer")
        .with_commands(["uv pip install --no-cache /opt/stargazer"])
    )


def released_image(name: str, release: str) -> str:
    """Where a release publishes a task image, tagged with its version.

    `release` is the package version as installed (`importlib.metadata`
    normalizes it, so tag `v2026.11.04` publishes `2026.11.4`).
    `cli/publish_task_images.py` pushes there, and an installed package pulls
    from there.
    """
    return f"ghcr.io/stargazerbio/{name}:{release}"


def _checkout() -> bool:
    """Whether the package runs from a checkout, which can build its images.

    Installed from PyPI, `PROJECT_ROOT` is the environment's `lib/python3.x`,
    which holds no `pyproject.toml`.
    """
    return (PROJECT_ROOT / "pyproject.toml").is_file()


def task_image(env: str | Path) -> flyte.Image:
    """A domain's task image, `stargazer-<domain>`: its `env.py`'s header, then the checkout.

    `env` is the domain's `env.py` (its `__file__`), whose PEP 723 header lists
    the environment's conda and PyPI packages, the released SDK among them,
    locked in the `env.py.pixi.lock` beside it (`cli/lock_envs.py`). Flyte
    renders the header as a pixi workspace and installs it from the header and
    lock alone, so that layer (Python, the tools, every dependency) is cached
    until either changes, and pixi's environment is the pod's Python. The
    checkout goes on top of the released SDK, and uv adds any core dependency
    it has gained since the release.

    An installed package has no checkout to build from: it runs on the image
    its release built this way and published (`released_image()`), so nothing
    builds.
    """
    env = Path(env)
    name = f"stargazer-{env.parent.name}"
    if not _checkout():
        return flyte.Image.from_base(released_image(name, version("stargazer-bio")))
    image = flyte.Image.from_pixi_script(env, name=name, platform=IMAGE_PLATFORM)
    return _with_source(image)


# The PEP 723 block, as Flyte's pixi script parser reads it.
_SCRIPT_BLOCK = re.compile(r"(?m)^# /// script\s*$\s(?:^#(?: .*)?$\s)*?^# ///\s*$")


def _header_without_sdk_source(notebook: Path) -> str:
    """`notebook`'s PEP 723 block, less its `[tool.pixi.pypi-dependencies]` SDK line."""
    block = _SCRIPT_BLOCK.search(notebook.read_text()).group(0)
    table = ""
    kept = []
    for line in block.splitlines():
        text = line.removeprefix("#").strip()
        if text.startswith("["):
            table = text
        if table == "[tool.pixi.pypi-dependencies]" and text.startswith(
            "stargazer-bio"
        ):
            continue
        kept.append(line)
    return "\n".join(kept) + "\n"


def notebook_image(notebook: str | Path, name: str) -> flyte.Image:
    """The image a notebook's own tasks run on: its header, then the SDK on top.

    `notebook` is the notebook's file (its `__file__`), whose PEP 723 header
    lists what its cells and tasks use. The header's `stargazer-bio` source in
    `[tool.pixi.pypi-dependencies]` is the SDK a notebook pod holds
    (`/stargazer`), which no image build has, so the build reads a copy of the
    header without it, under `STARGAZER_LOCAL`, and `stargazer-bio` installs
    from PyPI. Flyte names the image by the manifest the header renders to, so
    the kernel and a cluster pod, each with its own copy, name the same image.
    The SDK then goes on top: a checkout's source, or the release of the
    installed version. marimo writes no lock for a header, so the image
    resolves its packages anew whenever it's built.
    """
    header = _header_without_sdk_source(Path(notebook))
    digest = hashlib.sha256(header.encode()).hexdigest()[:16]
    script = (
        Path(os.environ["STARGAZER_LOCAL"])
        / "notebook-headers"
        / digest
        / Path(notebook).name
    )
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(header)
    image = flyte.Image.from_pixi_script(script, name=name, platform=IMAGE_PLATFORM)
    if not _checkout():
        return image.with_pip_packages(f"stargazer-bio=={version('stargazer-bio')}")
    return _with_source(image)
