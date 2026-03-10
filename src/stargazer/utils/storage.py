"""
### Storage abstraction for Stargazer.

Defines the StorageClient protocol, StargazerMode enum, and factory function
for creating storage clients based on STARGAZER_MODE configuration.

Configuration:
    STARGAZER_MODE=local (default)  -> local exec, local storage (or Pinata if JWT present)
    STARGAZER_MODE=cloud            -> union exec, Pinata storage (PINATA_JWT required)

spec: [docs/architecture/modes.md](../architecture/modes.md)
"""

import os
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol

from stargazer.types.asset import Asset


class StorageClient(Protocol):
    """Protocol defining the storage client interface.

    All storage backends (local, Pinata) implement this interface.
    """

    local_dir: Path

    async def upload(self, component: Asset) -> None:
        """Upload a file from component.path; sets component.cid.
        """
        ...

    async def download(
        self,
        component: Asset,
        dest: Optional[Path] = None,
    ) -> None:
        """Download a file by cid; sets component.path.
        """
        ...

    async def query(
        self,
        keyvalues: dict[str, str],
    ) -> list[Asset]:
        """Query files by keyvalue metadata; returns Asset list.
        """
        ...

    async def delete(self, component: Asset) -> None:
        """Delete a file from storage.
        """
        ...


class StargazerMode(Enum):
    """Execution and storage mode for Stargazer.
    """

    LOCAL = "local"
    CLOUD = "cloud"


def resolve_mode() -> StargazerMode:
    """Resolve the current Stargazer mode from STARGAZER_MODE env var.

    Returns:
        StargazerMode.LOCAL or StargazerMode.CLOUD

    Raises:
        ValueError: If STARGAZER_MODE is set to an invalid value
    """
    mode_str = os.environ.get("STARGAZER_MODE", "local").lower()
    try:
        return StargazerMode(mode_str)
    except ValueError:
        raise ValueError(
            f"Invalid STARGAZER_MODE: '{mode_str}'. Must be 'local' or 'cloud'."
        )


def get_client() -> StorageClient:
    """Create a storage client based on STARGAZER_MODE and available credentials.

    Resolution logic:
        - STARGAZER_MODE=cloud -> PinataClient (PINATA_JWT required)
        - STARGAZER_MODE=local + PINATA_JWT -> PinataClient
        - STARGAZER_MODE=local (no JWT) -> LocalStorageClient

    Returns:
        A StorageClient implementation
    """
    mode = resolve_mode()
    pinata_jwt = os.environ.get("PINATA_JWT")

    if mode == StargazerMode.CLOUD:
        if not pinata_jwt:
            raise ValueError("PINATA_JWT is required when STARGAZER_MODE=cloud.")
        from stargazer.utils.pinata import PinataClient

        return PinataClient()

    # Local mode: upgrade to Pinata if JWT is available
    if pinata_jwt:
        from stargazer.utils.pinata import PinataClient

        return PinataClient()

    from stargazer.utils.local_storage import LocalStorageClient

    return LocalStorageClient()


# Default module-level client instance.
# Configured via environment variables:
# - STARGAZER_MODE: "local" (default) or "cloud"
# - PINATA_JWT: Pinata JWT token (required in cloud mode, enables Pinata in local mode)
# - PINATA_GATEWAY: IPFS gateway URL (only when using Pinata)
# - STARGAZER_LOCAL: Local directory for files (default: ~/.stargazer/local)
default_client: StorageClient = get_client()
