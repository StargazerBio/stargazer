"""Call one Stargazer MCP tool over stdio, the way an agent harness does.

Starts the MCP server (`python -m stargazer.server`) from this uv environment
as a subprocess, calls the tool with the JSON arguments, and prints its text
result. The server inherits this process's environment, so the Launch block's
STARGAZER_* paths and empty PINATA_JWT apply to it. To drive another checkout's
server, run this with `uv run --directory <checkout>`.

Usage:
    uv run python .claude/skills/verify-stargazer/scripts/mcp_call.py <tool> ['<json args>']

Exits 1 when the tool reports an error.
"""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call(tool: str, args: dict) -> int:
    """Call one tool, print its text content, and return 1 if it errored."""
    # stdio_client passes the server only a few safe variables by default.
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "stargazer.server"], env=dict(os.environ)
    )
    async with (
        stdio_client(server) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(tool, args)
    for block in result.content:
        print(getattr(block, "text", block))
    return 1 if result.is_error else 0


if __name__ == "__main__":
    tool = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    sys.exit(asyncio.run(call(tool, args)))
