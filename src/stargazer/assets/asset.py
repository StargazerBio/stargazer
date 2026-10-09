"""
### Asset base dataclass for Stargazer.

An Asset is a file plus typed metadata. `cid` is the file's IPFS CID,
computed locally; `path` is a `flyte.io.File` naming where the stored bytes
live (the object store, or an IPFS gateway for public data), so an asset
passed between tasks always points somewhere every pod can read.
`fetch()` makes a local copy, with its companions beside it, and returns
its path.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Self, get_type_hints

from flyte.io import File

_BASE_FIELDS = frozenset(("cid", "path", "keyvalues"))


def _as_file(value: Any) -> File | None:
    """Coerce a local path or URI to a File named after its last segment."""
    if value is None or isinstance(value, File):
        return value
    location = str(value)
    return File(path=location, name=location.rstrip("/").rsplit("/", 1)[-1])


@dataclass
class Asset:
    """Base class for all typed file assets in Stargazer.

    Attributes:
        cid: IPFS CID of the stored file
        path: The stored file as a `flyte.io.File`. Assigning a local `Path`
            or a URI string wraps it in a File, so an asset can be built from
            a local file that was never uploaded; `fetch()` then uses that
            file in place.
        keyvalues: Free-form metadata for *bare* Asset instances — the
            catchall for records whose asset key has no registered class
            in this process. Serialized verbatim (the ``asset`` key lives
            inside the dict). Typed subclasses ignore this field entirely;
            they serialize their declared fields instead.

    Subclasses declare typed fields as normal dataclass attributes:

        @dataclass
        class Alignment(Asset):
            _asset_key: ClassVar[str] = "alignment"
            sample_id: str = ""
            duplicates_marked: bool = False

    Fields are plain Python attributes. ``to_keyvalues()`` serializes them to
    ``dict[str, str]`` at storage boundaries; ``from_keyvalues()`` reconstructs
    from storage. ``str`` fields pass through directly; all other types use
    ``json.dumps`` / ``json.loads``.
    """

    _registry: ClassVar[dict[str, type["Asset"]]] = {}
    _asset_key: ClassVar[str] = ""

    cid: str = ""
    path: File | None = None
    keyvalues: dict[str, str] = field(default_factory=dict)

    def __init_subclass__(cls, **kwargs):
        """Register subclass in the asset registry."""
        super().__init_subclass__(**kwargs)
        ak = cls.__dict__.get("_asset_key", "")
        if ak:
            Asset._registry[ak] = cls

    def __setattr__(self, name: str, value: Any) -> None:
        """Enforce declared fields on typed subclasses and coerce `path` to a File."""
        if name == "path":
            value = _as_file(value)
        elif self._asset_key and not name.startswith("_") and name not in _BASE_FIELDS:
            allowed = {f.name for f in dataclasses.fields(type(self))} - _BASE_FIELDS
            if name not in allowed:
                raise AttributeError(
                    f"{type(self).__name__} has no field '{name}'. "
                    f"Allowed: {sorted(allowed)}"
                )
        super().__setattr__(name, value)

    def to_keyvalues(self) -> dict[str, str]:
        """Serialize to storage format.

        str fields pass through as-is; all other types are serialized with
        json.dumps. Bare Asset instances return a copy of their keyvalues
        dict verbatim — a copy so callers (e.g. ``_owner`` stamping at the
        storage layer) can mutate the result without touching the Asset.
        """
        if not self._asset_key:
            return dict(self.keyvalues)
        hints = get_type_hints(type(self))
        result: dict[str, str] = {"asset": self._asset_key}
        for f in dataclasses.fields(self):
            if f.name in _BASE_FIELDS:
                continue
            val = getattr(self, f.name)
            result[f.name] = val if hints.get(f.name) is str else json.dumps(val)
        return result

    @classmethod
    def from_keyvalues(
        cls, kv: dict[str, str], cid: str = "", path: File | Path | str | None = None
    ) -> "Asset":
        """Reconstruct from a storage keyvalues dict.

        str fields are assigned directly; all other types are deserialized
        with json.loads (raising ``json.JSONDecodeError`` on values that
        don't parse — callers that must tolerate malformed records catch it,
        see ``specialize()``). Bare Asset receives the keyvalues verbatim.
        """
        if not cls._asset_key:
            return cls(cid=cid, path=path, keyvalues=dict(kv))
        hints = get_type_hints(cls)
        kwargs = {}
        for f in dataclasses.fields(cls):
            if f.name in _BASE_FIELDS:
                continue
            if f.name in kv:
                kwargs[f.name] = (
                    kv[f.name] if hints.get(f.name) is str else json.loads(kv[f.name])
                )
        return cls(cid=cid, path=path, **kwargs)

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict: the file's location and name."""
        return {
            "cid": self.cid,
            "path": self.path.path if self.path else None,
            "name": self.path.name if self.path else None,
            "keyvalues": self.to_keyvalues(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Reconstruct from a serialized dict."""
        path = None
        if data.get("path"):
            path = _as_file(data["path"])
            if data.get("name"):
                path = File(path=path.path, name=data["name"])
        return cls.from_keyvalues(
            data.get("keyvalues", {}), cid=data.get("cid", ""), path=path
        )

    async def fetch(self) -> Path:
        """Make a local copy of this asset and its companions; return its path.

        The asset lands at `<STARGAZER_LOCAL>/<cid>/<name>`, and every asset
        that names it via ``{_asset_key}_cid`` (indices, dictionaries, and
        any output that records it as a source) lands in the same directory,
        where tools look for them. An
        asset built from a local file that was never uploaded is returned in
        place. Copies already on disk are reused.
        """
        import stargazer.utils.storage as _storage

        local = await _storage.default_client.download(self)
        if self._asset_key and self.cid:
            for companion in await assemble(**{f"{self._asset_key}_cid": self.cid}):
                await _storage.default_client.download(companion, local.parent)
        return local

    async def update(self, path: Path, **kwargs) -> None:
        """Store a local file as this asset, setting fields from kwargs first.

        Sets `cid` and `path` (the stored File) once the file is uploaded and
        its index row has committed. Raises if either fails.
        """
        import stargazer.utils.storage as _storage

        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        await _storage.default_client.upload(self, Path(path))


async def assemble(**filters: Any) -> list["Asset"]:
    """Query storage by keyvalue filters and return specialized assets.

    Every filter must match exactly. A list value matches any of its entries
    (`asset=["r1", "r2"]`). Searches the user's index and, when a Pinata key
    is configured, the public tier; one asset per CID.

    Args:
        **filters: Keyvalue filters; values are strings or lists of strings

    Returns:
        Flat list of specialized Asset subclass instances.

    Examples:
        assets = await assemble(build="GRCh38", asset="reference")
        ref = next(a for a in assets if isinstance(a, Reference))

        assets = await assemble(sample_id="NA12878", asset=["r1", "r2"])
        r1 = next(a for a in assets if isinstance(a, R1))
    """
    import stargazer.utils.storage as _storage
    from stargazer.assets import specialize

    records = await _storage.default_client.query(filters)
    return [specialize(r) for r in records]
