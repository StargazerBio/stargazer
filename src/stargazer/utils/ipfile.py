"""
IpFile dataclass for representing files stored in IPFS or local storage.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class IpFile:
    """Represents a file stored in IPFS (via Pinata or other service)."""

    id: str
    cid: str
    name: Optional[str]
    size: int
    keyvalues: dict[str, str]
    created_at: datetime
    local_path: Optional[Path] = None  # Local cached file path
    is_public: bool = False  # Whether file is on public IPFS (vs private Pinata)

    @classmethod
    def from_api_response(cls, data: dict) -> "IpFile":
        """Parse from Pinata API JSON response."""
        # Determine visibility from network field (defaults to private if not present)
        network = data.get("network", "private")
        is_public = network == "public"

        return cls(
            id=data["id"],
            cid=data["cid"],
            name=data.get("name"),
            size=data["size"],
            keyvalues=data.get("keyvalues", {}),
            created_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
            local_path=None,
            is_public=is_public,
        )

    def public_url(self, gateway: str = "https://ipfs.io") -> Optional[str]:
        """Get public gateway URL. Returns None if file is private."""
        if self.is_public:
            return f"{gateway}/ipfs/{self.cid}"
        return None
