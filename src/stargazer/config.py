"""
### Centralized configuration for Stargazer.

Sets environment variable defaults at import time. Consumers read
os.environ directly rather than importing named values from this module.

Also the single source of truth for every Stargazer container image:
the lean per-task envs (`scrna_env`, `gatk_env`) and the heavy host envs
(`note_env`, `chat_env`). `stargazer-build-images` builds and pushes
all of them in one shot.

Rules:
- PINATA_JWT: No default — absence means no authenticated Pinata.
- PINATA_GATEWAY: Defaults to dweb.link if unset.
  Set to empty string to force a failure on public downloads.
- PINATA_VISIBILITY: Defaults to "private" if unset.
  Only evaluated by PinataClient — if JWT is unset, downloads are always public.
- STARGAZER_LOCAL: Local storage directory. Defaults to ~/.stargazer/local.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import inspect
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import flyte
import flyte.app
from loguru import logger as logger  # noqa: PLC0414

PROJECT_ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("PINATA_GATEWAY", "https://dweb.link")
os.environ.setdefault("PINATA_VISIBILITY", "private")
os.environ.setdefault("STARGAZER_LOCAL", str(Path.home() / ".stargazer" / "local"))

_log_dir = Path.home() / ".stargazer" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
logger.remove()
logger.add(_log_dir / "stargazer.log", rotation="10 MB", retention=5)


STARGAZER_ENV_VARS = {
    "PINATA_GATEWAY": os.environ.get("PINATA_GATEWAY", "https://dweb.link"),
    "PINATA_VISIBILITY": os.environ.get("PINATA_VISIBILITY", "private"),
}

STARGAZER_SECRETS = flyte.Secret(key="PINATA_JWT", as_env_var="PINATA_JWT")


def log_execution() -> str:
    """Start a per-execution log sink and return the execution ID.

    Derives the workflow name from the calling function, fetches the current
    git commit hash, and creates a dedicated logfile for this execution.
    Warns if the git tree has uncommitted changes.
    """
    workflow = inspect.currentframe().f_back.f_code.co_name
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip() or "unknown"

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        commit += "-dirty"
        logger.warning("Git tree is dirty — uncommitted changes present")

    execution_id = f"{workflow}-{commit}-{timestamp}"
    logger.add(_log_dir / f"{execution_id}.log")
    logger.info(f"Execution started: {execution_id}")
    return execution_id


# Shared mamba/bioconda layer used by the heavy `note` and `chat` images.
# Mirrors the `base` stage of the legacy Dockerfile so notebooks and the dev
# harness ship with bwa, bwa-mem2, samtools, and gatk4 preinstalled.
_BIOCONDA_INSTALL = [
    'curl -fsSL "https://github.com/conda-forge/miniforge/releases/latest/download/'
    'Miniforge3-Linux-$(uname -m).sh" -o /tmp/miniforge.sh '
    "&& bash /tmp/miniforge.sh -b -p /opt/conda && rm /tmp/miniforge.sh",
    "/opt/conda/bin/mamba install -y -c bioconda -c conda-forge "
    "bwa bwa-mem2 samtools gatk4 && /opt/conda/bin/mamba clean -afy",
]
_BIOCONDA_PATH = {
    "PATH": "/opt/conda/bin:/opt/conda/condabin:/usr/local/bin:/usr/bin:/bin",
}


# scRNA-seq task environment for scanpy-based single-cell analysis.
# Lean image: scanpy on top of the Flyte debian base. Memory-hungry at
# runtime because scanpy loads full AnnData objects into RAM.
scrna_env = flyte.TaskEnvironment(
    name="scrna",
    description="scanpy-based single-cell RNA analysis; memory-intensive AnnData workloads",
    image=(
        flyte.Image.from_debian_base()
        .with_apt_packages("ca-certificates")
        .with_pip_packages("scanpy>=1.12")
    ),
    resources=flyte.Resources(cpu=4, memory="32Gi"),
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)

# GATK/alignment task environment for GATK, BWA, and samtools tools.
# Lean image: leans on the upstream broadinstitute/gatk container, which
# ships the JVM, samtools, and bwa.
gatk_env = flyte.TaskEnvironment(
    name="gatk",
    description="GATK, BWA, and samtools alignment and variant-calling workloads",
    image=flyte.Image.from_base("broadinstitute/gatk"),
    resources=flyte.Resources(cpu=4, memory="16Gi"),
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)

# Heavy notebook runtime — replaces the Dockerfile `note` target.
# Used by `flyte serve` to host the marimo notebook UI; preloads bioconda
# CLIs and the full stargazer dependency tree (incl. the project itself)
# so tutorials run end-to-end without pip-installing on the fly.
note_env = flyte.app.AppEnvironment(
    name="stargazer-notebooks",
    description="Marimo notebook server preloaded with stargazer deps and bioconda tools",
    image=(
        flyte.Image.from_debian_base(python_version=(3, 13))
        .with_apt_packages("ca-certificates", "curl", "wget", "unzip", "git", "bzip2")
        .with_commands(_BIOCONDA_INSTALL)
        .with_env_vars(_BIOCONDA_PATH)
        .with_uv_project(
            pyproject_file=PROJECT_ROOT / "pyproject.toml",
            project_install_mode="install_project",
        )
    ),
    args=[sys.executable, "src/stargazer/app.py", "--server"],
    port=8080,
    include=["src/stargazer/notebooks/"],
    resources=flyte.Resources(cpu=2, memory="4Gi"),
    requires_auth=False,
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)

# Heavy agentic interface to the Stargazer MCP server — replaces the
# Dockerfile `chat` target. End users pull this image to drive Stargazer
# through Claude Code or OpenCode with the MCP server pre-wired. Bundles
# bioconda CLIs, Node.js + opencode, Claude Code, and the stargazer
# runtime deps so the agent can run pipelines (e.g. the scrna workflow)
# locally or dispatch heavier ones to a remote Flyte backend. No tasks
# decorate against it; it exists as a `flyte.Environment` so
# `stargazer-build-images` builds and pushes it alongside the others.
# Source contributors install natively (`uv sync --group dev`) — chat is
# not a dev shell.
chat_env = flyte.TaskEnvironment(
    name="chat",
    description="Agentic interface to the Stargazer MCP server",
    image=(
        flyte.Image.from_debian_base(python_version=(3, 13))
        .with_apt_packages("ca-certificates", "curl", "wget", "unzip", "git", "bzip2")
        .with_commands(
            _BIOCONDA_INSTALL
            + [
                "curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - "
                "&& apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*",
                "npm install -g opencode-ai",
                "curl -fsSL https://claude.ai/install.sh | bash "
                "&& install -m 755 /root/.local/bin/claude /usr/local/bin/claude",
            ]
        )
        .with_env_vars(_BIOCONDA_PATH)
        .with_uv_project(
            pyproject_file=PROJECT_ROOT / "pyproject.toml",
            project_install_mode="install_project",
        )
    ),
    resources=flyte.Resources(cpu=2, memory="8Gi"),
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)
