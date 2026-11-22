"""
### Stargazer MCP Server.

Exposes storage tools and a dynamic task runner via the MCP SDK's
high-level `MCPServer`.
Tasks and workflows are auto-discovered from the registry and executed
with `flyte.run`: remotely when `init_flyte()` finds an endpoint in
`.flyte/config.yaml`, in-process otherwise.

Usage:
    stargazer              # stdio transport (default)
    stargazer --http       # streamable-http transport

spec: [docs/architecture/mcp-server.md](../architecture/mcp-server.md)
"""

import json
import os
import sys
import types as _types
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, get_args, get_origin

import aiohttp
import flyte
from mcp.server import MCPServer

# MCPServer passes only a ToolError's message on to the client; any other
# exception reaches it as a bare "Error executing tool", its text kept in the
# server's log. So a refusal the caller has to act on is a ToolError.
from mcp.server.mcpserver.exceptions import ToolError

import stargazer.bundles as _bundles
import stargazer.utils.storage as _storage
from stargazer.assets import build_asset
from stargazer.assets.asset import Asset, specialize
from stargazer.config import init_flyte
from stargazer.marshal import marshal_output
from stargazer.registry import TaskInfo, TaskRegistry


@contextmanager
def _refusals() -> Iterator[None]:
    """Re-raise the storage layer's refusals as ToolErrors, keeping their message.

    `build_asset()`, the storage client and the bundles refuse a call the
    caller can fix (a missing `asset` key, a CID not in the index, no public
    tier, a path with no file) with a `ValueError` or `FileNotFoundError`.
    """
    try:
        yield
    except (ValueError, FileNotFoundError) as exc:
        raise ToolError(str(exc)) from exc


def _asset_class(hint: Any) -> tuple[type[Asset], bool] | None:
    """The Asset class a parameter's hint takes, and whether it takes a list.

    Handles `Asset`, `list[Asset]` and `Asset | None`. None for any other
    hint (scalars, dicts, lists of scalars).
    """
    if isinstance(hint, type) and issubclass(hint, Asset):
        return hint, False
    args = [a for a in get_args(hint) if a is not type(None)]
    if get_origin(hint) is list and args:
        inner = _asset_class(args[0])
        return (inner[0], True) if inner and not inner[1] else None
    if isinstance(hint, _types.UnionType) and len(args) == 1:
        return _asset_class(args[0])
    return None


async def _asset_by_cid(param: str, cid: Any, cls: type[Asset]) -> Asset:
    """The asset the index holds under `cid`, specialized, checked to be a `cls`."""
    if not isinstance(cid, str):
        raise ToolError(f"{param}: expected a CID string, got {cid!r}")
    row = await _storage.get_client().index.get(cid)
    if row is None:
        raise ToolError(
            f"{param}: no asset with CID {cid!r} in your index. Store it "
            "first (upload_file, or fetch_resource_bundle for a public file)."
        )
    asset = specialize(row)
    if not isinstance(asset, cls):
        raise ToolError(
            f"{param} takes a {cls.__name__}, but CID {cid!r} is of type "
            f"{type(asset).__name__}"
        )
    return asset


# ---------------------------------------------------------------------------
# MCPServer instance + registry
# ---------------------------------------------------------------------------

mcp = MCPServer("stargazer")

# flyte.init() gives Flyte's logger a Rich handler, which writes to stdout,
# the stdio transport, so its warnings would reach the client as lines that
# aren't JSON-RPC. Without Rich, Flyte logs to stderr.
os.environ.setdefault("DISABLE_RICH_LOGGING", "1")
init_flyte()
_registry = TaskRegistry()

# ---------------------------------------------------------------------------
# Storage tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def query_files(keyvalues: dict[str, str]) -> list[dict]:
    """Query files by metadata key-value pairs. Returns matching files."""
    return await _storage.get_client().query(keyvalues)


@mcp.tool()
async def upload_file(path: str, keyvalues: dict[str, str]) -> dict:
    """Upload a file with metadata key-value pairs.

    keyvalues must include "asset". Registered asset keys (e.g.
    asset=reference) check their declared fields' values, and keep any other
    key you supply (e.g. lane=3) as an extra text field on the typed asset,
    so tasks that take that type can still use the file. Unregistered keys
    are stored as generic assets with the keyvalues verbatim. Reserved
    system keys (underscore-prefixed, e.g. _owner) are stamped automatically
    and must not be supplied.

    When displaying results, always show a table with the CID and all keyvalues.
    """
    client = _storage.get_client()
    with _refusals():
        comp = build_asset(keyvalues)
        await client.upload(comp, Path(path))
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
    client = _storage.get_client()
    try:
        return str(await client.download(Asset(cid=cid)))
    except aiohttp.ClientResponseError as exc:
        raise ToolError(
            f"{cid} isn't in your storage, and the public gateway refused it "
            f"({exc.status} {exc.message})"
        ) from exc


@mcp.tool()
async def delete_file(cid: str) -> str:
    """Delete a file by CID."""
    await _storage.get_client().delete(Asset(cid=cid))
    return f"Deleted file {cid}"


@mcp.tool()
async def update_file(cid: str, keyvalues: dict[str, str]) -> dict:
    """Update (merge) metadata on an existing file by CID — fix a typo'd or
    mis-tagged record without re-uploading the bytes (the CID is unchanged).

    keyvalues is a patch onto your own index row: the supplied keys are added
    or overwritten, keys you omit are preserved (there is no key removal). It must
    include "asset"; the patch validates through the same rules as upload
    (registered keys check their declared fields' values and accept extra
    keys as text; reserved underscore keys like _owner are stamped
    automatically and must not be supplied).

    When displaying results, always show a table with the CID and all keyvalues.
    """
    client = _storage.get_client()
    with _refusals():
        build_asset(keyvalues)
        return await client.update_metadata(cid, keyvalues)


@mcp.tool()
async def publish_file(cid: str) -> list[dict]:
    """Publish one of your stored files and its companions (files whose
    `companion_of` is its CID, such as a reference's indices): anyone on the
    internet can then find and download them. The CIDs don't change, and your
    own copies stay. A companion that's already public isn't sent again.

    Needs the public tier (a Pinata key). Refused for a CID that isn't in your
    storage, and when any file in the set has metadata over the public tier's
    limits (nine fields, 250 characters each), before anything is sent.

    Returns a record (cid, name, keyvalues) for each file that went public,
    the file itself first. When displaying results, always show a table with
    the CID, name and all keyvalues of each.
    """
    client = _storage.get_client()
    with _refusals():
        return await client.publish(cid)


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
    with _refusals():
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
async def run_task(task_name: str, inputs: dict | None = None) -> dict:
    """Run a single task by name for ad-hoc experimentation.

    Every parameter goes in inputs by name. A parameter whose type is an
    asset (Reference, R1, Alignment...) takes the CID of a stored file of
    that type, found with query_files; a list of assets (list[KnownSites])
    takes a list of CIDs. Other parameters take their values as JSON.
    Optional parameters can be left out. A CID that isn't in your storage,
    or is the wrong type for its parameter, is refused.

        run_task("bwa_mem2_mem", {"ref": "bafk…", "r1": "bafk…", "r2": "bafk…"})

    For reproducible pipeline runs, use run_workflow instead.

    Args:
        task_name: Name of the task (from list_tasks with category="task").
        inputs: The task's keyword arguments: CIDs for asset parameters,
                values for the rest.

    Returns:
        Serialized task output. Single outputs returned directly,
        multi-outputs as {"o0": ..., "o1": ...}.
    """
    info = _registry.get(task_name)
    if info is None:
        available = [t.name for t in _registry.list_tasks(category="task")]
        raise ToolError(f"Unknown task: {task_name!r}. Available: {available}")
    if info.category != "task":
        raise ToolError(f"{task_name!r} is a workflow — use run_workflow instead.")

    inputs = inputs or {}
    params = {p.name: p for p in info.params}
    unknown = sorted(set(inputs) - set(params))
    if unknown:
        raise ToolError(
            f"{task_name!r} has no parameter {unknown[0]!r}. "
            f"Its parameters: {list(params)}"
        )
    missing = [p.name for p in info.params if p.required and p.name not in inputs]
    if missing:
        raise ToolError(f"{task_name!r} requires {missing[0]!r}")

    kwargs = {}
    for name, value in inputs.items():
        asset = _asset_class(params[name].type_hint)
        if asset is None or value is None:
            kwargs[name] = value
        elif asset[1]:
            if not isinstance(value, list):
                raise ToolError(f"{name}: expected a list of CIDs, got {value!r}")
            kwargs[name] = [await _asset_by_cid(name, cid, asset[0]) for cid in value]
        else:
            kwargs[name] = await _asset_by_cid(name, value, asset[0])

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
        raise ToolError(f"Unknown workflow: {workflow_name!r}. Available: {available}")
    if info.category != "workflow":
        raise ToolError(f"{workflow_name!r} is a task — use run_task instead.")

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
