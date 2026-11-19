"""
### Centralized configuration for Stargazer.

Sets environment variable defaults at import time. Consumers read
os.environ directly rather than importing named values from this module.

Also the logger, and what every task environment shares besides its image:
the secrets forwarded into its pods. The environments themselves live in
their domains' `env.py` (`stargazer.tasks.scrna.env`,
`stargazer.tasks.gatk.env`), their images in `stargazer.images`.
The variables a pod needs reach a hosted project's task pods from the
project's settings; `STARGAZER_ENV_VARS` forwards the submitter's for a
cluster whose projects don't carry them (the devbox).

`init_flyte()` is the one Flyte init for notebooks, the MCP server and the
tests: an in-cluster client in a hosted notebook pod, the config file anywhere
else.

Rules:
- PINATA_JWT: No default — absence means no public tier (Pinata) at all.
- PINATA_GATEWAY: IPFS gateway for public downloads. Defaults to the project's
  dedicated Pinata gateway.
- STARGAZER_LOCAL: Temp space for task outputs and the download cache.
  Defaults to ~/.stargazer/local.
- STARGAZER_STORE_ROOT: Where asset bytes are stored — a local directory or a
  bucket URI (e.g. `s3://stargazerbio-users`). Defaults
  to ~/.stargazer/store.
- STARGAZER_INDEX_URL: The asset index — a SQLite file path, a
  `postgresql://` URL (the devbox's), or a `dsql://` URL naming a user's
  table on Aurora DSQL (Union's). Defaults to ~/.stargazer/index.db.
  A cluster task with either at its local default raises
  (`require_cluster_storage()`).
- STARGAZER_OWNER: The Union subject that owns new assets (their folder in
  the store, and `_owner`). Unset locally.
- STARGAZER_API_KEY_SECRET: The Flyte secret holding the project's API key.
  When it's set, every environment declares that secret, as the variable
  Flyte's in-cluster client reads its key from, so a pod can call the cluster
  as its project. Union needs one; a cluster without a login (the devbox), or
  a local run, leaves it unset. Forwarded into every pod.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import contextlib
import os
import sys
from pathlib import Path

import flyte
from loguru import logger as logger  # noqa: PLC0414

from stargazer.images import _checkout

# The account's dedicated gateway, since public ones rate-limit full
# downloads. Every download through it, signed in or not, counts against the
# account's bandwidth.
os.environ.setdefault(
    "PINATA_GATEWAY", "https://maroon-written-fowl-769.mypinata.cloud"
)
os.environ.setdefault("STARGAZER_LOCAL", str(Path.home() / ".stargazer" / "local"))

# The local defaults: a store and index on this machine's disk.
_LOCAL_STORAGE = {
    "STARGAZER_STORE_ROOT": str(Path.home() / ".stargazer" / "store"),
    "STARGAZER_INDEX_URL": str(Path.home() / ".stargazer" / "index.db"),
}

# Storage locations set explicitly (a deploy, a pod's env) are forwarded into
# task pods; the local defaults aren't, since a pod can't use them.
_STORAGE_KEYS = tuple(_LOCAL_STORAGE)
_EXPLICIT_STORAGE = {k: os.environ[k] for k in _STORAGE_KEYS if os.environ.get(k)}
for _key, _default in _LOCAL_STORAGE.items():
    os.environ.setdefault(_key, _default)

_log_dir = Path.home() / ".stargazer" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
logger.remove()
logger.add(_log_dir / "stargazer.log", rotation="10 MB", retention=5)
logger.add(sys.stderr, level="INFO")


def _stargazer_env_vars() -> dict[str, str]:
    """The submitter's variables, for a TaskEnvironment on a cluster whose projects don't carry them.

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


def require_cluster_storage() -> None:
    """Refuse to store on a cluster pod's own disk.

    A pod's disk goes with the pod, so an asset stored there is gone before
    the next task looks for it. Flyte's task context says whether this is a
    cluster pod; a local run, and anything outside a task, keeps the local
    defaults.

    Raises:
        RuntimeError: in a cluster task whose store or index is the local
            default, naming the variables that are missing.
    """
    ctx = flyte.ctx()
    if not ctx or not ctx.is_in_cluster():
        return
    missing = [k for k, default in _LOCAL_STORAGE.items() if os.environ[k] == default]
    if missing:
        raise RuntimeError(
            f"{' and '.join(missing)} not set in this task's pod, so it would "
            "store assets on its own disk, where no other task can find them. "
            "A hosted project's settings give them to every task pod; on a "
            "cluster that doesn't, pass env_vars=STARGAZER_ENV_VARS "
            "(stargazer.config) to the task's TaskEnvironment."
        )


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
