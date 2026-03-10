"""
### Asset base dataclass for Stargazer.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from typing_extensions import Self

_MISSING = object()


@dataclass
class Asset:
    """Base class for all typed file assets in Stargazer.

    Attributes:
        cid: Content identifier (CID) for the stored file
        path: Local filesystem path (set after download or upload)
        keyvalues: Metadata key-value pairs for querying and routing

    Subclasses declare typed field annotations directly:

        @dataclass
        class Alignment(Asset):
            _asset_key: ClassVar[str] = "alignment"
            sample_id: str = ""
            duplicates_marked: bool = False

    ``__init_subclass__`` auto-derives ``_field_types`` (non-str fields) and
    ``_field_defaults`` (all defaults) from the annotations. The ``_field_types``
    and ``_field_defaults`` ClassVars on the base class are empty-dict defaults
    inherited by subclasses that declare no fields.
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
        """Register subclass in the asset registry and derive field metadata."""
        super().__init_subclass__(**kwargs)
        ak = cls.__dict__.get("_asset_key", "")
        if ak:
            Asset._registry[ak] = cls

        field_types: dict[str, type] = {}
        field_defaults: dict[str, Any] = {}
        for name, annotation in cls.__dict__.get("__annotations__", {}).items():
            if name.startswith("_"):
                continue
            if typing.get_origin(annotation) is ClassVar:
                continue
            if annotation is not str:
                field_types[name] = annotation
            default = cls.__dict__.get(name, _MISSING)
            if default is not _MISSING:
                field_defaults[name] = default

        if field_types:
            cls._field_types = field_types
        if field_defaults:
            cls._field_defaults = field_defaults

    def __post_init__(self):
        """Seed the 'asset' keyvalue from _asset_key on construction."""
        if self._asset_key:
            self.keyvalues.setdefault("asset", self._asset_key)

    def __getattribute__(self, name: str) -> Any:
        """Read declared fields from keyvalues with type coercion; delegate everything else."""
        # Fast-path: internal/private attrs skip all keyvalues logic
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        # Get the field registries without triggering recursion
        field_defaults = object.__getattribute__(self, "_field_defaults")
        field_types = object.__getattribute__(self, "_field_types")

        # Only intercept declared fields; let everything else through
        if name in field_defaults or name in field_types:
            try:
                kv = object.__getattribute__(self, "keyvalues")
            except AttributeError:
                return object.__getattribute__(self, name)
            val = kv.get(name)
            ftype = field_types.get(name)
            if val is None:
                if ftype is bool:
                    return field_defaults.get(name, False)
                return field_defaults.get(name)
            if ftype is bool:
                return val == "true"
            if ftype is int:
                return int(val)
            if ftype is list:
                return val.split(",") if val else None
            return val

        return object.__getattribute__(self, name)

    def __getattr__(self, name: str) -> Any:
        """Fall back to keyvalues lookup for undeclared attributes on base Asset."""
        # Fallback for undeclared keys on base Asset instances
        kv = self.__dict__.get("keyvalues", {})
        return kv.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Coerce and store declared fields into keyvalues; bypass for core attrs."""
        if name in self._own_attrs or name.startswith("_"):
            super().__setattr__(name, value)
            return
        # Enforce allowed keys — only on subclasses that declare _asset_key
        if self._asset_key:
            allowed = (
                frozenset(self._field_defaults)
                | frozenset(self._field_types)
                | {"asset"}
            )
            if name not in allowed:
                raise ValueError(
                    f"{type(self).__name__} does not allow keyvalue '{name}'. "
                    f"Allowed: {sorted(allowed)}"
                )
        # Coerce and store in keyvalues
        ftype = self._field_types.get(name)
        if ftype is bool:
            # Preserve already-serialized strings; coerce bool/other by truthiness
            if isinstance(value, str):
                self.keyvalues[name] = "true" if value == "true" else "false"
            else:
                self.keyvalues[name] = "true" if value else "false"
        elif isinstance(value, bool):
            self.keyvalues[name] = "true" if value else "false"
        elif ftype is list or isinstance(value, list):
            if value is None:
                self.keyvalues[name] = ""
            elif isinstance(value, list):
                self.keyvalues[name] = ",".join(value)
            else:
                self.keyvalues[name] = str(value)
        else:
            self.keyvalues[name] = str(value)

    async def fetch(self) -> None:
        """Download this asset and all its companions from storage.

        Downloads the asset itself, then queries storage for any assets linked
        via ``{_asset_key}_cid`` to auto-download companions (e.g. indices,
        mate reads).
        """
        import stargazer.utils.storage as _storage

        await _storage.default_client.download(self)

        if self._asset_key and self.cid:
            companions = await assemble(**{f"{self._asset_key}_cid": self.cid})
            for a in companions:
                await _storage.default_client.download(a)

    async def update(self, path: Path, **kwargs) -> None:
        """Upload file and set cid. Shared by all asset types.
        """
        from stargazer.utils.storage import default_client

        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict.
        """
        return {
            "cid": self.cid,
            "path": str(self.path) if self.path else None,
            "keyvalues": self.keyvalues,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Reconstruct from a serialized dict.
        """
        kv = data.get("keyvalues", {})
        if cls._asset_key:
            # Subclass: unpack declared fields as kwargs; keyvalues rebuilt by __setattr__
            declared = set(cls._field_defaults) | set(cls._field_types)
            field_kwargs = {k: v for k, v in kv.items() if k in declared}
            return cls(
                cid=data.get("cid", ""),
                path=Path(data["path"]) if data.get("path") else None,
                **field_kwargs,
            )
        # Base Asset: pass keyvalues directly
        return cls(
            cid=data.get("cid", ""),
            path=Path(data["path"]) if data.get("path") else None,
            keyvalues=dict(kv),
        )


async def assemble(**filters: Any) -> list["Asset"]:
    """Query storage by keyvalue filters and return specialized assets.

    The ``asset`` filter key accepts a string or list of strings to narrow
    by asset type. Other filters are passed through as keyvalue matchers.

    Args:
        **filters: Keyvalue filters. Values may be scalars or lists
                   (cartesian product).

    Returns:
        Flat list of specialized Asset subclass instances.

    Examples:
        assets = await assemble(build="GRCh38", asset="reference")
        ref = next(a for a in assets if isinstance(a, Reference))

        assets = await assemble(sample_id="NA12878", asset=["r1", "r2"])
        r1 = next(a for a in assets if isinstance(a, R1))
    """
    import stargazer.utils.storage as _storage
    from stargazer.types import specialize
    from stargazer.utils.query import generate_query_combinations

    query_combinations = generate_query_combinations(base_query={}, filters=filters)

    seen: dict[str, Asset] = {}
    for query in query_combinations:
        for raw in await _storage.default_client.query(query):
            seen[raw.cid] = raw

    return [specialize(a) for a in seen.values()]
