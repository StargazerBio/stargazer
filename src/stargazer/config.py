"""
### Centralized configuration for Stargazer.

Sets environment variable defaults at import time. Consumers read
os.environ directly rather than importing named values from this module.

Also the source of truth for the lean per-task Flyte environments
(`scrna_env`, `gatk_env`). The user-facing AppEnvironment lives in
`infra/app.py` alongside the FastAPI application it deploys.

Rules:
- PINATA_JWT: No default — absence means no public tier (Pinata) at all.
- PINATA_GATEWAY: IPFS gateway for public downloads. Defaults to dweb.link.
- PINATA_VISIBILITY: Defaults to "private". Read only by the asset-manager
  page's direct Pinata calls; the SDK's storage uses Pinata's public network.
- STARGAZER_LOCAL: Scratch space for task outputs and the download cache.
  Defaults to ~/.stargazer/local.
- STARGAZER_STORE_ROOT: Where asset bytes are stored — a local directory or a
  bucket URI (e.g. `s3://union-us-west-2-stargazerbio/stargazer`). Defaults
  to ~/.stargazer/store.
- STARGAZER_INDEX_URL: The asset index — a SQLite file path, or a user's
  dashboard URL on Union. Defaults to ~/.stargazer/index.db.
- STARGAZER_OWNER: The Union subject that owns new assets (their folder in
  the store, and `_owner`). Unset locally.
- STARGAZER_TARGET: Which Flyte backend images and deploys aim at — `devbox`
  (default, the local cluster) or `union` (the hosted tenant). Anything else
  is an error. Forwarded into every pod so in-pod builds resolve the same way.
- STARGAZER_REGISTRY: Image push registry. Defaults to the devbox's in-cluster
  registry on `devbox`; left unset on `union`, where the remote builder pushes
  to Union's own registry. An explicit value wins on either target.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import inspect
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import flyte
from loguru import logger as logger  # noqa: PLC0414

PROJECT_ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("PINATA_GATEWAY", "https://dweb.link")
os.environ.setdefault("PINATA_VISIBILITY", "private")
os.environ.setdefault("STARGAZER_LOCAL", str(Path.home() / ".stargazer" / "local"))

# Storage locations set explicitly (a deploy, a pod's env) are forwarded into
# task pods; the local defaults below are not, since a pod can't use them.
_STORAGE_KEYS = ("STARGAZER_STORE_ROOT", "STARGAZER_INDEX_URL")
_EXPLICIT_STORAGE = {k: os.environ[k] for k in _STORAGE_KEYS if os.environ.get(k)}
os.environ.setdefault("STARGAZER_STORE_ROOT", str(Path.home() / ".stargazer" / "store"))
os.environ.setdefault(
    "STARGAZER_INDEX_URL", str(Path.home() / ".stargazer" / "index.db")
)

TARGETS = ("devbox", "union")
os.environ.setdefault("STARGAZER_TARGET", "devbox")
if os.environ["STARGAZER_TARGET"] not in TARGETS:
    raise ValueError(
        f"STARGAZER_TARGET={os.environ['STARGAZER_TARGET']!r}; expected one of {TARGETS}"
    )
if os.environ["STARGAZER_TARGET"] == "devbox":
    os.environ.setdefault("STARGAZER_REGISTRY", "localhost:30000")

_log_dir = Path.home() / ".stargazer" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
logger.remove()
logger.add(_log_dir / "stargazer.log", rotation="10 MB", retention=5)
logger.add(sys.stderr, level="INFO")


def _stargazer_env_vars() -> dict[str, str]:
    """env_vars forwarded into task pods via the TaskEnvironments.

    The spec serializes from the submitting process, so STARGAZER_OWNER is
    included when the submitter carries it (hosted workspaces) — task pods
    then stamp ``_owner`` onto pipeline outputs. Strictly optional: absent
    locally, nothing requires it. STARGAZER_TARGET (and an explicit
    STARGAZER_REGISTRY) ride along so a pod that builds or submits images —
    the admin app, a notebook, a parent task — resolves them like the deployer.
    STARGAZER_STORE_ROOT and STARGAZER_INDEX_URL ride along only when set
    explicitly: a pod can't use the local store or index.
    """
    env = {
        "PINATA_GATEWAY": os.environ.get("PINATA_GATEWAY", "https://dweb.link"),
        "STARGAZER_TARGET": os.environ["STARGAZER_TARGET"],
        **_EXPLICIT_STORAGE,
    }
    registry = os.environ.get("STARGAZER_REGISTRY")
    if registry:
        env["STARGAZER_REGISTRY"] = registry
    owner = os.environ.get("STARGAZER_OWNER")
    if owner:
        env["STARGAZER_OWNER"] = owner
    return env


STARGAZER_ENV_VARS = _stargazer_env_vars()

STARGAZER_SECRETS = [flyte.Secret(key="PINATA_JWT", as_env_var="PINATA_JWT")]


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

    jwt_len = len(os.environ.get("PINATA_JWT", ""))
    logger.info(
        f"Execution started: {execution_id} "
        f"| store={os.environ['STARGAZER_STORE_ROOT']} "
        f"| index={os.environ['STARGAZER_INDEX_URL']} "
        f"| public tier={'on' if jwt_len else 'off'} "
        f"| gateway={os.environ['PINATA_GATEWAY']} "
        f"| local_dir={os.environ['STARGAZER_LOCAL']} | target={os.environ['STARGAZER_TARGET']}"
    )
    return execution_id


# scRNA-seq task environment for scanpy-based single-cell analysis.
# Lean image: scanpy on top of the Flyte debian base. Memory-hungry at
# runtime because scanpy loads full AnnData objects into RAM.
scrna_env = flyte.TaskEnvironment(
    name="scrna",
    description="scanpy-based single-cell RNA analysis; memory-intensive AnnData workloads",
    image=(
        flyte.Image.from_debian_base(
            name="stargazer-scrna",
            registry=os.environ.get("STARGAZER_REGISTRY"),
        )
        .with_apt_packages("ca-certificates")
        .with_pip_packages("scanpy>=1.12")
        .with_uv_project(PROJECT_ROOT / "pyproject.toml")
    ),
    resources=flyte.Resources(memory=("2Gi", "6Gi")),
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)

# GATK/alignment task environment for GATK, BWA, and samtools tools.
# Multi-arch Debian base with micromamba layered on. gatk4, samtools, bwa,
# and bwa-mem2 all come from bioconda (which publishes native linux-aarch64
# and linux-64 builds). Conda env lives at /opt/conda; binaries symlinked
# onto PATH so tasks invoke them directly.
gatk_env = flyte.TaskEnvironment(
    name="gatk",
    description="GATK, BWA, and samtools alignment and variant-calling workloads",
    image=(
        flyte.Image.from_debian_base(
            name="stargazer-gatk",
            registry=os.environ.get("STARGAZER_REGISTRY"),
            platform=("linux/amd64", "linux/arm64"),
        )
        .with_apt_packages("ca-certificates", "curl", "bzip2")
        .with_commands(
            [
                # Install micromamba (arch-detected) into /usr/local/bin.
                'arch=$(uname -m); case "$arch" in x86_64) marc=linux-64;; '
                "aarch64|arm64) marc=linux-aarch64;; esac; "
                "curl -Ls https://micro.mamba.pm/api/micromamba/${marc}/latest "
                "| tar -xj -C /usr/local/bin --strip-components=1 bin/micromamba",
                # Create the conda env at /opt/conda with the bioinformatics tools.
                "/usr/local/bin/micromamba create -p /opt/conda -y "
                "-c bioconda -c conda-forge gatk4 samtools bwa bwa-mem2 "
                "&& /usr/local/bin/micromamba clean -a -y",
                # Expose the conda binaries on the default PATH. java is the JVM
                # bundled by the gatk4 conda package; gatk's wrapper script
                # subprocess-calls it by name so it must be on PATH.
                "ln -s /opt/conda/bin/gatk /usr/local/bin/gatk "
                "&& ln -s /opt/conda/bin/java /usr/local/bin/java "
                "&& ln -s /opt/conda/bin/samtools /usr/local/bin/samtools "
                "&& ln -s /opt/conda/bin/bwa /usr/local/bin/bwa "
                "&& ln -s /opt/conda/bin/bwa-mem2 /usr/local/bin/bwa-mem2",
            ]
        )
        .with_uv_project(PROJECT_ROOT / "pyproject.toml")
    ),
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)
