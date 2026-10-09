"""
### Stargazer MCP Server.

Exposes storage tools and a dynamic task runner via the MCP SDK's
high-level `MCPServer` (named `FastMCP` before SDK 2.0).
Tasks and workflows are auto-discovered from the registry and executed
with `flyte.run`: remotely when `flyte.init_from_config()` finds an
endpoint in `.flyte/config.yaml`, in-process otherwise.

Usage:
    stargazer              # stdio transport (default)
    stargazer --http       # streamable-http transport

spec: [docs/architecture/mcp-server.md](../architecture/mcp-server.md)
"""

import json
import os
import sys
import types as _types
from pathlib import Path
from typing import Any, get_args, get_origin

import flyte
from mcp.server import MCPServer

import stargazer.bundles as _bundles
import stargazer.config  # ensure env var defaults are set  # noqa: F401
import stargazer.utils.storage as _storage
from stargazer.assets import build_asset
from stargazer.assets.asset import Asset, assemble
from stargazer.marshal import marshal_output
from stargazer.registry import TaskInfo, TaskRegistry


def _asset_key_for_hint(hint: Any) -> str | None:
    """Extract the _asset_key from a type hint, if it's an Asset type.

    Handles plain Asset subclasses, list[Asset], and unions containing Assets.
    Returns None for non-Asset hints (scalars, Path, etc.).
    """
    if isinstance(hint, type) and issubclass(hint, Asset) and hint._asset_key:
        return hint._asset_key

    origin = get_origin(hint)
    args = get_args(hint)

    if origin is list and args:
        inner = args[0]
        if isinstance(inner, type) and issubclass(inner, Asset) and inner._asset_key:
            return inner._asset_key

    if isinstance(hint, _types.UnionType) and args:
        for arg in args:
            if arg is type(None):
                continue
            key = _asset_key_for_hint(arg)
            if key:
                return key

    return None


def _is_list_asset_hint(hint: Any) -> bool:
    """True if the hint is list[AssetSubclass]."""
    origin = get_origin(hint)
    args = get_args(hint)
    if origin is list and args:
        inner = args[0]
        return isinstance(inner, type) and issubclass(inner, Asset)
    return False


# ---------------------------------------------------------------------------
# MCPServer instance + registry
# ---------------------------------------------------------------------------

mcp = MCPServer("stargazer")

flyte.init_from_config()
_registry = TaskRegistry()

# ---------------------------------------------------------------------------
# Storage tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def query_files(keyvalues: dict[str, str]) -> list[dict]:
    """Query files by metadata key-value pairs. Returns matching files."""
    return await _storage.default_client.query(keyvalues)


@mcp.tool()
async def upload_file(path: str, keyvalues: dict[str, str]) -> dict:
    """Upload a file with metadata key-value pairs.

    keyvalues must include "asset". Registered asset keys (e.g.
    asset=reference) validate strictly against their declared fields;
    unregistered keys are stored as generic assets with the keyvalues
    verbatim. Reserved system keys (underscore-prefixed, e.g. _owner) are
    stamped automatically and must not be supplied.

    When displaying results, always show a table with the CID and all keyvalues.
    """
    comp = build_asset(keyvalues)
    await _storage.default_client.upload(comp, Path(path))
    result = comp.to_dict()
    if type(comp) is Asset:
        result["note"] = (
            f"asset key {keyvalues['asset']!r} is not registered; stored as a "
            "generic asset"
        )
    return result


@mcp.tool()
async def download_file(cid: str) -> str:
    """Download a file by CID to local cache. Returns the local path.

    A CID that isn't in your index is treated as public and fetched from the
    IPFS gateway.
    """
    return str(await _storage.default_client.download(Asset(cid=cid)))


@mcp.tool()
async def delete_file(cid: str) -> str:
    """Delete a file by CID."""
    await _storage.default_client.delete(Asset(cid=cid))
    return f"Deleted file {cid}"


@mcp.tool()
async def update_file(cid: str, keyvalues: dict[str, str]) -> dict:
    """Update (merge) metadata on an existing file by CID — fix a typo'd or
    mis-tagged record without re-uploading the bytes (the CID is unchanged).

    keyvalues is a patch: the supplied keys are added or overwritten, keys
    you omit are preserved (Pinata merge — there is no key removal). It must
    include "asset"; the patch validates through the same rules as upload
    (registered keys check their declared fields; reserved underscore keys
    like _owner are stamped automatically and must not be supplied).

    When displaying results, always show a table with the CID and all keyvalues.
    """
    build_asset(keyvalues)  # validate the patch (raises ValueError on bad input)
    return await _storage.default_client.update_metadata(cid, keyvalues)


# ---------------------------------------------------------------------------
# Bundle tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_bundles() -> list[dict]:
    """List available resource bundles.

    Returns:
        List of bundles with name, description, and file_count.
    """
    return _bundles.list_bundles()


@mcp.tool()
async def fetch_resource_bundle(bundle_name: str) -> list[dict]:
    """Download a predefined resource bundle into local storage.

    Bundles are curated sets of public files (e.g. reference genomes, demo
    datasets) defined in the codebase. Each file is downloaded by CID from
    the public IPFS gateway and recorded in the user's index with the
    manifest's keyvalues, so assemble() and query_files find it afterwards,
    with or without a Pinata key.

    Args:
        bundle_name: Name of the bundle (from list_bundles).

    Returns:
        List of fetched files with cid, name, keyvalues, local path, and
        whether each was already cached.
    """
    return await _bundles.fetch_bundle(bundle_name)


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
    assemble() resolves all required assets, and every filter must match
    each asset, so assets with different keys (a reference's build, a
    sample's sample_id) can't be filled from one call. Scalar and Path
    parameters are passed separately via inputs.

    For reproducible pipeline runs, use run_workflow instead.

    Args:
        task_name: Name of the task (from list_tasks with category="task").
        filters: Keyvalue filters for assemble() to resolve asset parameters
                 (e.g. {"asset": "reference", "build": "GRCh38"}); a list
                 value matches any of its entries.
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
    assets = await assemble(**filters) if filters else []

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
    """Run a Flyte task/workflow and return marshalled output."""
    run = flyte.run(info.task_obj, **kwargs)
    run.wait()
    named = run.outputs().named_outputs  # {"o0": value, ...}
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
    """Show current Stargazer configuration and available task counts."""
    tasks = _registry.list_tasks(category="task")
    workflows = _registry.list_tasks(category="workflow")
    config = {
        "pinata_jwt": "set" if os.environ.get("PINATA_JWT") else "unset",
        "store_root": os.environ["STARGAZER_STORE_ROOT"],
        "index": os.environ["STARGAZER_INDEX_URL"],
        "local_dir": os.environ["STARGAZER_LOCAL"],
        "tasks": len(tasks),
        "workflows": len(workflows),
    }
    return json.dumps(config, indent=2)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    """Run the Stargazer MCP server."""
    transport = "stdio"
    if "--http" in sys.argv:
        transport = "streamable-http"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
