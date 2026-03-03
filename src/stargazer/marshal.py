"""Output marshaling: typed object → dict (for MCP response serialization)."""

from pathlib import Path
from typing import Any


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
