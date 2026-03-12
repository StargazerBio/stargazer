"""
### Centralized configuration for Stargazer.

Sets environment variable defaults at import time. Consumers read
os.environ directly rather than importing named values from this module.

Rules:
- PINATA_JWT: No default — absence means no authenticated Pinata.
- PINATA_GATEWAY: Defaults to gateway.pinata.cloud if unset.
  Set to empty string to force a failure on public downloads.
- PINATA_VISIBILITY: Defaults to "private" if unset.
  Only evaluated by PinataClient — if JWT is unset, downloads are always public.
- STARGAZER_LOCAL: Local storage directory. Defaults to ~/.stargazer/local.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import os
from pathlib import Path

import flyte
from loguru import logger as logger  # noqa: PLC0414

os.environ.setdefault("PINATA_GATEWAY", "https://gateway.pinata.cloud")
os.environ.setdefault("PINATA_VISIBILITY", "private")
os.environ.setdefault("STARGAZER_LOCAL", str(Path.home() / ".stargazer" / "local"))

_log_dir = Path.home() / ".stargazer" / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)
logger.remove()
logger.add(_log_dir / "stargazer.log", rotation="10 MB", retention=5)

# GATK task environment for GATK-specific tools
# Uses GATK image with Java runtime and GATK tools
gatk_env = flyte.TaskEnvironment(
    name="gatk",
    image=flyte.Image.from_base("broadinstitute/gatk"),
    resources=flyte.Resources(
        cpu=4,
        memory="16Gi",
    ),
    cache="auto",
)
