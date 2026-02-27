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

from stargazer.marshal import marshal_input, marshal_output
from stargazer.registry import TaskRegistry
from stargazer.utils.component import ComponentFile
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
    """Upload a file with metadata key-value pairs."""
    comp = ComponentFile(path=Path(path), keyvalues=keyvalues)
    await default_client.upload(comp)
    return comp.to_dict()


@mcp.tool()
async def download_file(cid: str) -> str:
    """Download a file by CID to local cache. Returns the local path."""
    comp = ComponentFile(cid=cid)
    await default_client.download(comp)
    return str(comp.path)


@mcp.tool()
async def delete_file(cid: str) -> str:
    """Delete a file by CID."""
    comp = ComponentFile(cid=cid)
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
def run_task(task_name: str, inputs: dict) -> dict:
    """Run any registered task or workflow by name using Flyte local execution.

    Accepts JSON-friendly inputs (dicts for domain types like Reference,
    Alignment, etc.) and returns JSON-friendly outputs.

    Args:
        task_name: Name of the task or workflow (from list_tasks).
        inputs: Keyword arguments as a JSON dict. Domain types (Reference,
                Alignment, Reads, Variants, ComponentFile) should be passed as
                dicts matching their to_dict() format.

    Returns:
        Serialized task output. Single outputs returned directly,
        multi-outputs as {"o0": ..., "o1": ...}.
    """
    info = _registry.get(task_name)
    if info is None:
        available = [t.name for t in _registry.list_tasks()]
        raise ValueError(f"Unknown task: {task_name!r}. Available: {available}")

    # Build a lookup of param name → type hint
    param_hints = {p.name: p.type_hint for p in info.params}

    # Marshal each input from JSON-friendly to typed Python objects
    marshaled = {}
    for key, value in inputs.items():
        hint = param_hints.get(key)
        if hint is None:
            raise ValueError(
                f"Unknown parameter {key!r} for task {task_name!r}. "
                f"Expected: {list(param_hints.keys())}"
            )
        marshaled[key] = marshal_input(value, hint)

    # Execute via Flyte local run context
    run = _run_ctx.run(info.task_obj, **marshaled)
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
