"""
BioType base class for Stargazer.

Provides generic to_dict/from_dict/fetch via annotation introspection,
so container dataclasses (Reference, Alignment, etc.) need zero boilerplate.
"""

import types as _types
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from typing_extensions import Self

from stargazer.types.component import ComponentFile


def _unwrap_optional(hint: Any) -> Any:
    """Unwrap Optional[X] / X | None to X. Returns hint unchanged if not optional."""
    if isinstance(hint, _types.UnionType):
        non_none = [a for a in hint.__args__ if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    elif get_origin(hint) is Union:
        non_none = [a for a in get_args(hint) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return hint


def _is_component_type(hint: Any) -> bool:
    """Check if hint is a concrete ComponentFile subclass."""
    return isinstance(hint, type) and issubclass(hint, ComponentFile)


def _is_component_list(hint: Any) -> bool:
    """Check if hint is list[SomeComponentFile]."""
    if get_origin(hint) is list:
        args = get_args(hint)
        return bool(args) and _is_component_type(args[0])
    return False


@dataclass
class BioType:
    """Base class for container types that hold ComponentFile fields.

    Provides generic serialization via annotation introspection.
    Subclasses are pure dataclass declarations — no need to write
    to_dict, from_dict, or fetch.
    """

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        hints = get_type_hints(type(self))
        result: dict = {}
        for f in fields(self):
            value = getattr(self, f.name)
            hint = _unwrap_optional(hints[f.name])

            if _is_component_type(hint):
                if value is not None:
                    result[f.name] = value.to_dict()
            elif _is_component_list(hint):
                if value:
                    result[f.name] = [item.to_dict() for item in value]
            else:
                # Scalars, dicts, etc. — include if not None and not empty list
                if value is not None:
                    result[f.name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Reconstruct from a serialized dict."""
        hints = get_type_hints(cls)
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            hint = _unwrap_optional(hints[f.name])

            if _is_component_type(hint):
                kwargs[f.name] = hint.from_dict(value)
            elif _is_component_list(hint):
                item_type = get_args(hint)[0]
                kwargs[f.name] = [item_type.from_dict(item) for item in value]
            else:
                kwargs[f.name] = value
        return cls(**kwargs)

    async def fetch(self) -> Path:
        """Fetch all component files to local cache. Returns the cache directory."""
        from stargazer.utils.storage import default_client

        hints = get_type_hints(type(self))
        components: list[ComponentFile] = []
        for f in fields(self):
            hint = _unwrap_optional(hints[f.name])
            value = getattr(self, f.name)
            if _is_component_type(hint) and value is not None:
                components.append(value)
            elif _is_component_list(hint) and value:
                components.extend(value)

        if not components:
            raise ValueError(
                f"No files to fetch. {type(self).__name__} has no components set."
            )

        for c in components:
            await default_client.download(c)

        return default_client.local_dir
