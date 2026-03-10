"""
### Stargazer MCP Server.

Exposes storage tools and a dynamic task runner via FastMCP.
Tasks and workflows are auto-discovered from the registry and executed
through the Flyte local run context.

Usage:
    stargazer              # stdio transport (default)
    stargazer --http       # streamable-http transport

spec: [docs/architecture/mcp-server.md](../architecture/mcp-server.md)
"""

import json
import os
import types as _types
from pathlib import Path
from typing import Any, get_args, get_origin

import flyte
from mcp.server.fastmcp import FastMCP

from stargazer.marshal import marshal_output
from stargazer.registry import TaskInfo, TaskRegistry
from stargazer.types import ASSET_REGISTRY
from stargazer.types.asset import Asset
from stargazer.types.asset import assemble
from stargazer.utils.storage import default_client


def _asset_key_for_hint(hint: Any) -> str | None:
    """Extract the _asset_key from a type hint, if it's an Asset type.

    Handles plain Asset subclasses, list[Asset], and unions containing Assets.
    Returns None for non-Asset hints (scalars, Path, etc.).
    """
    # Direct Asset subclass
    if isinstance(hint, type) and issubclass(hint, Asset) and hint._asset_key:
        return hint._asset_key

    origin = get_origin(hint)
    args = get_args(hint)

    # list[AssetSubclass]
    if origin is list and args:
        inner = args[0]
        if isinstance(inner, type) and issubclass(inner, Asset) and inner._asset_key:
            return inner._asset_key

    # Union / X | Y — find the Asset branch
    if isinstance(hint, _types.UnionType) and args:
        for arg in args:
            if arg is type(None):
                continue
            key = _asset_key_for_hint(arg)
            if key:
                return key

    return None


def _is_list_asset_hint(hint: Any) -> bool:
    """True if the hint is list[AssetSubclass].
    """
    origin = get_origin(hint)
    args = get_args(hint)
    if origin is list and args:
        inner = args[0]
        return isinstance(inner, type) and issubclass(inner, Asset)
    return False


# ---------------------------------------------------------------------------
# FastMCP instance + registry
# ---------------------------------------------------------------------------

mcp = FastMCP("stargazer")

flyte.init_from_config()
_registry = TaskRegistry()

# ---------------------------------------------------------------------------
# Storage tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def query_files(keyvalues: dict[str, str]) -> list[dict]:
    """Query files by metadata key-value pairs. Returns matching files.
    """
    files = await default_client.query(keyvalues)
    return [f.to_dict() for f in files]


@mcp.tool()
async def upload_file(path: str, keyvalues: dict[str, str]) -> dict:
    """Upload a file with metadata key-value pairs.

    keyvalues must include "asset". Valid asset keys are derived
    from the Asset registry (e.g. asset=reference component=fasta).

    When displaying results, always show a table with the CID and all keyvalues.
    """
    asset_key = keyvalues.get("asset")
    if asset_key not in ASSET_REGISTRY:
        valid = sorted(ASSET_REGISTRY.keys())
        raise ValueError(f"Invalid asset key {asset_key!r}. Valid keys: {valid}")
    cls = ASSET_REGISTRY[asset_key]
    declared = set(cls._field_defaults) | set(cls._field_types)
    unknown = set(keyvalues) - declared - {"asset"}
    if unknown:
        raise ValueError(
            f"Unknown keys for {asset_key!r}: {unknown}. Allowed: {sorted(declared)}"
        )
    field_kwargs = {k: v for k, v in keyvalues.items() if k in declared}
    comp = cls(path=Path(path), **field_kwargs)
    await default_client.upload(comp)
    return comp.to_dict()


@mcp.tool()
async def download_file(cid: str) -> str:
    """Download a file by CID to local cache. Returns the local path.
    """
    comp = Asset(cid=cid)
    await default_client.download(comp)
    return str(comp.path)


@mcp.tool()
async def delete_file(cid: str) -> str:
    """Delete a file by CID.
    """
    comp = Asset(cid=cid)
    await default_client.delete(comp)
    return f"Deleted file {cid}"


# ---------------------------------------------------------------------------
# Dynamic task tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tasks(category: str | None = None) -> list[dict]:
    """List available tasks and workflows with their parameter signatures.

    Args:
        category: Filter by "task" or "workflow". Omit for all.

    Returns:
        Catalog of tasks with name, category, description, params, and outputs.
    """
    return _registry.to_catalog(category=category)


@mcp.tool()
async def run_task(task_name: str, filters: dict, inputs: dict | None = None) -> dict:
    """Run a single task by name for ad-hoc experimentation.

    Use this for testing individual tools in isolation. Asset parameters
    are assembled from storage using the provided filters — one call to
    assemble() resolves all required assets. Scalar and Path parameters
    are passed separately via inputs.

    For reproducible pipeline runs, use run_workflow instead.

    Args:
        task_name: Name of the task (from list_tasks with category="task").
        filters: Keyvalue filters for assemble() to resolve asset parameters
                 (e.g. {"build": "GRCh38", "sample_id": "NA12878"}).
        inputs: Optional scalar/Path keyword arguments (str, int, bool, list[str]).

    Returns:
        Serialized task output. Single outputs returned directly,
        multi-outputs as {"o0": ..., "o1": ...}.
    """
    info = _registry.get(task_name)
    if info is None:
        available = [t.name for t in _registry.list_tasks(category="task")]
        raise ValueError(f"Unknown task: {task_name!r}. Available: {available}")
    if info.category != "task":
        raise ValueError(f"{task_name!r} is a workflow — use run_workflow instead.")

    inputs = inputs or {}

    # Assemble all assets from storage in one query
    assets = await assemble(**filters) if filters else []

    # Build kwargs: match Asset params from the assembled list, scalars from inputs
    kwargs = {}
    for p in info.params:
        asset_key = _asset_key_for_hint(p.type_hint)
        if asset_key:
            matched = [a for a in assets if a._asset_key == asset_key]
            if not matched and p.required:
                raise ValueError(
                    f"Task {task_name!r} requires {p.name} ({asset_key}) "
                    f"but no matching asset found for filters: {filters}"
                )
            if matched:
                kwargs[p.name] = (
                    matched if _is_list_asset_hint(p.type_hint) else matched[-1]
                )
        elif p.name in inputs:
            value = inputs[p.name]
            if p.type_hint is Path and isinstance(value, str):
                value = Path(value)
            kwargs[p.name] = value

    return await _execute(info, kwargs)


@mcp.tool()
async def run_workflow(workflow_name: str, inputs: dict) -> dict:
    """Run a workflow by name for reproducible pipeline execution.

    Workflows accept scalar parameters (str, int, bool, list[str]) and
    handle their own asset assembly internally. Pass inputs exactly as
    the workflow signature defines them — no automatic resolution is
    performed.

    For ad-hoc experimentation with individual tools, use run_task instead.

    Args:
        workflow_name: Name of the workflow (from list_tasks with category="workflow").
        inputs: Keyword arguments as a JSON dict (scalars only).

    Returns:
        Serialized workflow output. Single outputs returned directly,
        multi-outputs as {"o0": ..., "o1": ...}.
    """
    info = _registry.get(workflow_name)
    if info is None:
        available = [t.name for t in _registry.list_tasks(category="workflow")]
        raise ValueError(f"Unknown workflow: {workflow_name!r}. Available: {available}")
    if info.category != "workflow":
        raise ValueError(f"{workflow_name!r} is a task — use run_task instead.")

    return await _execute(info, dict(inputs))


async def _execute(info: TaskInfo, kwargs: dict) -> dict:
    """Run a Flyte task/workflow and return marshalled output.
    """
    run = flyte.run(info.task_obj, **kwargs)
    run.wait()
    named = run.outputs().named_outputs  # {"o0": value, ...}

    # Unwrap single outputs; keep dict for multi-output tasks
    if len(named) == 1:
        result = next(iter(named.values()))
    else:
        result = named

    return marshal_output(result)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("stargazer://config")
async def show_config() -> str:
    """Show current Stargazer configuration and available task counts.
    """
    tasks = _registry.list_tasks(category="task")
    workflows = _registry.list_tasks(category="workflow")
    config = {
        "stargazer_mode": os.environ.get("STARGAZER_MODE", "local"),
        "local_dir": str(default_client.local_dir),
        "tasks": len(tasks),
        "workflows": len(workflows),
    }
    return json.dumps(config, indent=2)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    """Run the Stargazer MCP server.
    """
    import sys

    transport = "stdio"
    if "--http" in sys.argv:
        transport = "streamable-http"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
