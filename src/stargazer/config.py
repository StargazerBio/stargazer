"""
### Centralized configuration for Stargazer.

All environment variables are resolved here at import time.
Consumers import values from this module rather than reading os.environ directly.

Rules:
- If the env var is set (even to empty string), use that value exactly.
- If the env var is unset, apply the default.
- PINATA_JWT: None if unset (no default — absence means no authenticated Pinata).
- PINATA_GATEWAY: Public IPFS gateway URL. Defaults to gateway.pinata.cloud if unset.
  Set to empty string to force a failure on public downloads.
- PINATA_VISIBILITY: "public" or "private". Defaults to "private" if unset.
  Only evaluated by PinataClient — if JWT is unset, downloads are always public.
- STARGAZER_LOCAL: Local storage directory. Defaults to ~/.stargazer/local.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import os
from pathlib import Path

import flyte
from loguru import logger as logger  # noqa: PLC0414


def _env_or_default(key: str, default: str) -> str:
    """Return env var value if set (even if empty), otherwise default."""
    sentinel = object()
    val = os.environ.get(key, sentinel)
    if val is sentinel:
        return default
    return val


STARGAZER_LOCAL: Path = Path(
    _env_or_default("STARGAZER_LOCAL", str(Path.home() / ".stargazer" / "local"))
)

PINATA_JWT: str | None = os.environ.get("PINATA_JWT") or None

PINATA_GATEWAY: str = _env_or_default("PINATA_GATEWAY", "https://gateway.pinata.cloud")

PINATA_VISIBILITY: str = _env_or_default("PINATA_VISIBILITY", "private").lower()

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
