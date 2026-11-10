"""
### Asset base dataclass for Stargazer.

An Asset is a file plus typed metadata. `cid` is the file's IPFS CID,
computed locally; `path` is a `flyte.io.File` naming where the stored bytes
live (the object store, or an IPFS gateway for public data), so an asset
passed between tasks always points somewhere every pod can read.
`fetch()` makes a local copy, with its companions beside it, and returns
its path. A companion is any asset whose `companion_of` keyvalue holds
another asset's CID: an index or a sequence dictionary that tools expect
beside the file it names.

Keyvalues a type doesn't declare ride along as `keyvalues`, its extras. A
task that builds a new asset from an input copies only the fields it sets, so
an input's extras don't pass to its output.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, get_type_hints

from flyte.io import File

from stargazer.config import logger

_BASE_FIELDS = frozenset(("cid", "path", "keyvalues"))

# Asset key -> class, filled by `Asset.__init_subclass__`.
ASSET_REGISTRY: dict[str, type[Asset]] = {}


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
        keyvalues: On a bare Asset, all of its metadata, serialized
            verbatim (the ``asset`` key lives inside the dict): the catchall
            for kinds of file with no registered class in this process. On
            a typed subclass, the extra keys its class doesn't declare,
            kept as strings and written beside the declared fields.

    Subclasses declare typed fields as normal dataclass attributes:

        @dataclass
        class Alignment(Asset):
            _asset_key: ClassVar[str] = "alignment"
            sample_id: str = ""
            duplicates_marked: bool = False

    Fields are plain Python attributes. ``to_keyvalues()`` serializes them to
    ``dict[str, str]`` at storage boundaries; ``from_keyvalues()`` reconstructs
    from storage. ``str`` fields pass through directly; all other types use
    ``json.dumps`` / ``json.loads``. ``declared_fields()`` lists a type's
    fields. Attributes are strict (assigning an undeclared one raises); extra
    keys go in ``keyvalues`` instead:

        aln.keyvalues["lane"] = "3"
    """

    _asset_key: ClassVar[str] = ""

    cid: str = ""
    path: File | None = None
    keyvalues: dict[str, str] = field(default_factory=dict)

    def __init_subclass__(cls, **kwargs):
        """Register subclass in the asset registry."""
        super().__init_subclass__(**kwargs)
        ak = cls.__dict__.get("_asset_key", "")
        if ak:
            ASSET_REGISTRY[ak] = cls

    def __setattr__(self, name: str, value: Any) -> None:
        """Enforce declared fields on typed subclasses and coerce `path` to a File."""
        if name == "path":
            value = _as_file(value)
        elif self._asset_key and not name.startswith("_") and name not in _BASE_FIELDS:
            allowed = self.declared_fields()
            if name not in allowed:
                raise AttributeError(
                    f"{type(self).__name__} has no field '{name}'. "
                    f"Allowed: {sorted(allowed)}"
                )
        super().__setattr__(name, value)

    @classmethod
    def declared_fields(cls) -> tuple[str, ...]:
        """Names of the fields this asset type declares, in declaration order.

        These are the typed keyvalues it reads and writes: every dataclass
        field except the base ``cid``, ``path`` and ``keyvalues``. Bare Asset
        declares none.
        """
        return tuple(
            f.name for f in dataclasses.fields(cls) if f.name not in _BASE_FIELDS
        )

    def to_keyvalues(self) -> dict[str, str]:
        """Serialize to storage format.

        str fields pass through as-is; all other types are serialized with
        json.dumps. A typed asset's extra keys are written beside its
        declared fields. Bare Asset instances return their keyvalues
        verbatim. The result is always a copy, so callers (e.g. ``_owner``
        stamping at the storage layer) can mutate it without touching the
        Asset.

        Raises:
            ValueError: when a typed asset's ``keyvalues`` holds ``asset``
                or one of its declared fields, which are set as attributes
        """
        if not self._asset_key:
            return dict(self.keyvalues)
        declared = self.declared_fields()
        clash = sorted(set(self.keyvalues) & {"asset", *declared})
        if clash:
            raise ValueError(
                f"{type(self).__name__}.keyvalues holds {clash}, which "
                f"{type(self).__name__} sets itself: assign the attribute instead"
            )
        hints = get_type_hints(type(self))
        result: dict[str, str] = {"asset": self._asset_key}
        for name in declared:
            val = getattr(self, name)
            result[name] = val if hints.get(name) is str else json.dumps(val)
        result.update(self.keyvalues)
        return result

    @classmethod
    def from_keyvalues(
        cls, kv: dict[str, str], cid: str = "", path: File | Path | str | None = None
    ) -> Asset:
        """Reconstruct from a storage keyvalues dict.

        str fields are assigned directly; all other types are deserialized
        with json.loads (raising ``json.JSONDecodeError`` on values that
        don't parse — callers that must tolerate malformed records catch it,
        see ``specialize()``). On a typed class, every key that isn't
        ``asset`` or a declared field becomes an extra in ``keyvalues``.
        Bare Asset receives the keyvalues verbatim.
        """
        if not cls._asset_key:
            return cls(cid=cid, path=path, keyvalues=dict(kv))
        hints = get_type_hints(cls)
        declared = cls.declared_fields()
        kwargs = {
            name: value if hints.get(name) is str else json.loads(value)
            for name, value in kv.items()
            if name in declared
        }
        extras = {k: v for k, v in kv.items() if k not in declared and k != "asset"}
        return cls(cid=cid, path=path, keyvalues=extras, **kwargs)

    def to_dict(self) -> dict:
        """Serialize to the storage record shape: `cid`, `uri`, `name`, `keyvalues`.

        The shape index rows and public records have, so `specialize()` reads
        it back.
        """
        return {
            "cid": self.cid,
            "uri": self.path.path if self.path else None,
            "name": self.path.name if self.path else None,
            "keyvalues": self.to_keyvalues(),
        }

    async def fetch(self) -> Path:
        """Make a local copy of this asset and its companions; return its path.

        The asset lands at `<STARGAZER_LOCAL>/<cid>/<name>`, and its
        companions (`StorageClient.companions`: an index, a sequence
        dictionary) land in the same directory, where tools look for them.
        Outputs that record it as an input under another key, such as an
        Alignment's ``reference_cid``, stay behind. An asset built from a
        local file that was never uploaded is returned in place. Copies
        already on disk are reused; a companion file left by an earlier fetch
        is replaced when a different one of that name is picked now. A
        companion named like the asset itself is skipped.
        """
        import stargazer.utils.storage as _storage

        client = _storage.default_client
        local = await client.download(self)
        if self.cid:
            for record in await client.companions(self.cid):
                if record["name"] != local.name:
                    await client.download(specialize(record), local.parent)
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


def specialize(record: dict) -> Asset:
    """Construct a typed Asset subclass from a raw storage record.

    Looks up the 'asset' key in the record's keyvalues against the registry
    and returns the appropriate subclass instance. Falls back to a bare
    Asset carrying the keyvalues verbatim when no type is registered in
    this process, or when the record's values don't parse against the
    registered class (strict at upload, graceful at query — one malformed
    legacy record must not crash a whole ``assemble()``).

    The record's ``uri`` and original ``name`` become the asset's ``path``
    (a `flyte.io.File`), so a later download lands on disk with the real
    extension (tools like GATK refuse CID-named inputs).
    """
    kv = record.get("keyvalues", {})
    cid = record.get("cid", "")
    path = None
    if record.get("uri"):
        path = File(path=record["uri"], name=record.get("name") or cid, hash=cid)
    cls = ASSET_REGISTRY.get(kv.get("asset", ""))
    if cls is None:
        return Asset(cid=cid, path=path, keyvalues=dict(kv))
    try:
        return cls.from_keyvalues(kv, cid=cid, path=path)
    except ValueError:
        logger.warning(
            f"Record {cid} claims asset={kv.get('asset')!r} but its values "
            f"don't parse as {cls.__name__}; returning it as a bare Asset"
        )
        return Asset(cid=cid, path=path, keyvalues=dict(kv))


def build_asset(keyvalues: dict[str, str]) -> Asset:
    """Construct an Asset from keyvalues, typed when the key is registered.

    The single validation choke point shared by the MCP server and the
    asset-manager page. A registered asset key builds its class: declared
    fields are parsed to their types, and any other key is kept as a
    string extra in ``keyvalues``. An unregistered key is first-class and
    constructs a bare Asset carrying the keyvalues verbatim (the catchall
    for kinds of file no class describes yet).

    Raises:
        ValueError: when ``keyvalues["asset"]`` is missing; when any key is
            underscore-prefixed (reserved system namespace — keys like
            ``_owner`` are stamped automatically at the storage layer, so
            callers must drop them); or when the asset key is registered and
            a declared non-``str`` field doesn't json-parse (strict at
            upload, vs. ``specialize()`` which degrades gracefully at query
            time).
    """
    asset_key = keyvalues.get("asset")
    if not asset_key:
        raise ValueError(
            "keyvalues must include 'asset'. Registered keys: "
            f"{sorted(ASSET_REGISTRY)}; unregistered keys are stored as "
            "generic assets."
        )
    reserved = sorted(k for k in keyvalues if k.startswith("_"))
    if reserved:
        raise ValueError(
            f"Reserved system keys {reserved} are stamped automatically — "
            "remove them from keyvalues."
        )
    cls = ASSET_REGISTRY.get(asset_key)
    if cls is None:
        return Asset(keyvalues=dict(keyvalues))
    return cls.from_keyvalues(keyvalues)


async def assemble(**filters: Any) -> list[Asset]:
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

    records = await _storage.default_client.query(filters)
    return [specialize(r) for r in records]
