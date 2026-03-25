"""
### Centralized configuration for Stargazer.

Sets environment variable defaults at import time. Consumers read
os.environ directly rather than importing named values from this module.

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
from datetime import datetime, timezone
from pathlib import Path

import flyte
from loguru import logger as logger  # noqa: PLC0414

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


# scRNA-seq task environment for scanpy-based single-cell analysis
# Memory-hungry: scanpy loads full AnnData objects into RAM
scrna_env = flyte.TaskEnvironment(
    name="scrna",
    description="scanpy-based single-cell RNA analysis; memory-intensive AnnData workloads",
    image=flyte.Image.from_debian_base().with_pip_packages("scanpy>=1.12"),
    resources=flyte.Resources(
        cpu=4,
        memory="32Gi",
    ),
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)

# GATK/alignment task environment for GATK, BWA, and samtools tools
# Uses GATK image with Java runtime, BWA, and samtools pre-installed
gatk_env = flyte.TaskEnvironment(
    name="gatk",
    description="GATK, BWA, and samtools alignment and variant-calling workloads",
    image=flyte.Image.from_base("broadinstitute/gatk"),
    resources=flyte.Resources(
        cpu=4,
        memory="16Gi",
    ),
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)
