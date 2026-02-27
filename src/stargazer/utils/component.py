"""
ComponentFile base dataclass for Stargazer.

Lives in utils to avoid circular imports — storage clients need ComponentFile,
and type modules need storage clients.
"""

from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import Self


@dataclass
class ComponentFile:
    """Base class for all typed file components in Stargazer.

    Attributes:
        cid: Content identifier (CID) for the stored file
        path: Local filesystem path (set after download or upload)
        keyvalues: Metadata key-value pairs for querying and routing
    """

    cid: str = ""
    path: Path | None = None
    keyvalues: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        return {
            "cid": self.cid,
            "path": str(self.path) if self.path else None,
            "keyvalues": self.keyvalues,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Reconstruct from a serialized dict."""
        return cls(
            cid=data.get("cid", ""),
            path=Path(data["path"]) if data.get("path") else None,
            keyvalues=data.get("keyvalues", {}),
        )
