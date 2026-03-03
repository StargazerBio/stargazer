"""
Asset base dataclass for Stargazer.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from typing_extensions import Self


@dataclass
class Asset:
    """Base class for all typed file assets in Stargazer.

    Attributes:
        cid: Content identifier (CID) for the stored file
        path: Local filesystem path (set after download or upload)
        keyvalues: Metadata key-value pairs for querying and routing

    Subclasses can declare:
        _field_types: map of field name -> type (bool, int, list) for coercion
        _field_defaults: map of field name -> default value (e.g. {"sample_id": ""})
        _asset_key: the "asset" keyvalue (e.g. "reference", "alignment")
    """

    _registry: ClassVar[dict[str, type["Asset"]]] = {}
    _field_types: ClassVar[dict[str, type]] = {}
    _field_defaults: ClassVar[dict[str, Any]] = {}
    _own_attrs: ClassVar[frozenset] = frozenset(("cid", "path", "keyvalues"))
    _asset_key: ClassVar[str] = ""

    cid: str = ""
    path: Path | None = None
    keyvalues: dict[str, str] = field(default_factory=dict)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        ak = cls.__dict__.get("_asset_key", "")
        if ak:
            Asset._registry[ak] = cls

    def __post_init__(self):
        if self._asset_key:
            self.keyvalues.setdefault("asset", self._asset_key)
        for k, v in self._field_defaults.items():
            self.keyvalues.setdefault(k, v)

    def __getattr__(self, name: str) -> Any:
        # Only called when normal attribute lookup fails
        kv = self.__dict__.get("keyvalues", {})
        val = kv.get(name)
        ftype = self._field_types.get(name)
        if val is None:
            if ftype is bool:
                return self._field_defaults.get(name, False)
            return self._field_defaults.get(name)
        if ftype is bool:
            return val == "true"
        if ftype is int:
            return int(val)
        if ftype is list:
            return val.split(",") if val else None
        return val

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._own_attrs or name.startswith("_"):
            super().__setattr__(name, value)
            return
        # Coerce and store in keyvalues
        ftype = self._field_types.get(name)
        if isinstance(value, bool) or ftype is bool:
            self.keyvalues[name] = "true" if value else "false"
        elif ftype is list or isinstance(value, list):
            self.keyvalues[name] = ",".join(value)
        else:
            self.keyvalues[name] = str(value)

    async def update(self, path: Path, **kwargs) -> None:
        """Upload file and set cid. Shared by all asset types."""
        from stargazer.utils.storage import default_client

        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)

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
