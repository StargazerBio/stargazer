"""Bidirectional type conversion between JSON dicts (MCP transport) and typed Python objects.

Input marshaling: dict → typed object (driven by registry type hints)
Output marshaling: typed object → dict (for MCP response serialization)
"""

import types as _types
from pathlib import Path
from typing import Any, Union, get_args, get_origin

from stargazer.types.component import ComponentFile
from stargazer.types.biotype import BioType
from stargazer.tasks.gatk.variant_recalibrator import VQSRResource


def marshal_input(value: Any, hint: Any) -> Any:
    """Convert a JSON-friendly value to the typed object expected by a task parameter."""
    if value is None:
        return None

    # Unwrap Optional (X | None)
    if _is_optional(hint):
        return marshal_input(value, _unwrap_optional(hint))

    origin = get_origin(hint)
    args = get_args(hint)

    # list[T]
    if origin is list and args:
        return [marshal_input(item, args[0]) for item in value]

    # Domain types with from_dict
    if (
        isinstance(hint, type)
        and issubclass(hint, (ComponentFile, BioType))
        and isinstance(value, dict)
    ):
        return hint.from_dict(value)

    # VQSRResource (no from_dict)
    if isinstance(hint, type) and hint is VQSRResource and isinstance(value, dict):
        return VQSRResource(**value)

    # Path
    if isinstance(hint, type) and issubclass(hint, Path):
        return Path(value)

    # Primitives / pass-through
    return value


def marshal_output(value: Any) -> Any:
    """Convert a typed Python object to a JSON-friendly structure for MCP transport."""
    if value is None:
        return None

    if hasattr(value, "to_dict"):
        return value.to_dict()

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, tuple):
        return {f"o{i}": marshal_output(item) for i, item in enumerate(value)}

    if isinstance(value, list):
        return [marshal_output(item) for item in value]

    if isinstance(value, dict):
        return {k: marshal_output(v) for k, v in value.items()}

    return value


def _is_optional(hint: Any) -> bool:
    """Check if a type hint is Optional (Union with None)."""
    if isinstance(hint, _types.UnionType):
        return type(None) in hint.__args__
    origin = get_origin(hint)
    if origin is Union:
        return type(None) in get_args(hint)
    return False


def _unwrap_optional(hint: Any) -> Any:
    """Unwrap Optional[X] to X."""
    if isinstance(hint, _types.UnionType):
        non_none = [a for a in hint.__args__ if a is not type(None)]
    else:
        non_none = [a for a in get_args(hint) if a is not type(None)]
    return non_none[0] if len(non_none) == 1 else hint
