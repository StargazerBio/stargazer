"""
Stargazer MCP Server.

Exposes storage tools and a dynamic task runner via FastMCP.
Tasks and workflows are auto-discovered from the registry and executed
through the Flyte local run context.

Usage:
    stargazer              # stdio transport (default)
    stargazer --http       # streamable-http transport
"""

import json
import os
from pathlib import Path

import flyte
from mcp.server.fastmcp import FastMCP

from stargazer.marshal import marshal_output
from stargazer.registry import TaskRegistry
from stargazer.types import ASSET_REGISTRY
from stargazer.types.asset import Asset
from stargazer.types.constellation import assemble
from stargazer.utils.storage import default_client

# ---------------------------------------------------------------------------
# FastMCP instance + registry
# ---------------------------------------------------------------------------

mcp = FastMCP("stargazer")

flyte.init_from_config()
_registry = TaskRegistry()
_run_ctx = flyte.with_runcontext(mode="local")

# ---------------------------------------------------------------------------
# Storage tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def query_files(keyvalues: dict[str, str]) -> list[dict]:
    """Query files by metadata key-value pairs. Returns matching files."""
    files = await default_client.query(keyvalues)
    return [f.to_dict() for f in files]


@mcp.tool()
async def upload_file(path: str, keyvalues: dict[str, str]) -> dict:
    """Upload a file with metadata key-value pairs.

    keyvalues must include "asset". Valid asset keys are derived
    from the Asset registry (e.g. asset=reference component=fasta).
    """
    asset_key = keyvalues.get("asset")
    if asset_key not in ASSET_REGISTRY:
        valid = sorted(ASSET_REGISTRY.keys())
        raise ValueError(f"Invalid asset key {asset_key!r}. Valid keys: {valid}")
    comp = Asset(path=Path(path), keyvalues=keyvalues)
    await default_client.upload(comp)
    return comp.to_dict()


@mcp.tool()
async def download_file(cid: str) -> str:
    """Download a file by CID to local cache. Returns the local path."""
    comp = Asset(cid=cid)
    await default_client.download(comp)
    return str(comp.path)


@mcp.tool()
async def delete_file(cid: str) -> str:
    """Delete a file by CID."""
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
async def run_task(task_name: str, inputs: dict) -> dict:
    """Run any registered task or workflow by name using Flyte local execution.

    Accepts JSON-friendly inputs (dicts for domain types like Reference,
    Alignment, etc.) and returns JSON-friendly outputs.

    Args:
        task_name: Name of the task or workflow (from list_tasks).
        inputs: Keyword arguments as a JSON dict. Domain types should be passed
                as filter dicts under the "filters" key for assembly
                (e.g. {"filters": {"build": "GRCh38", "asset": "reference"}}).

    Returns:
        Serialized task output. Single outputs returned directly,
        multi-outputs as {"o0": ..., "o1": ...}.
    """
    info = _registry.get(task_name)
    if info is None:
        available = [t.name for t in _registry.list_tasks()]
        raise ValueError(f"Unknown task: {task_name!r}. Available: {available}")

    # Assemble assets from storage filters, pass everything else as scalars
    filters = inputs.pop("filters", {})
    constellation = await assemble(**filters) if filters else None

    kwargs = dict(inputs)
    if constellation is not None:
        kwargs["data"] = constellation

    # Execute via Flyte local run context
    run = _run_ctx.run(info.task_obj, **kwargs)
    run.wait()
    result = run.outputs()

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
    """Run the Stargazer MCP server."""
    import sys

    transport = "stdio"
    if "--http" in sys.argv:
        transport = "streamable-http"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
