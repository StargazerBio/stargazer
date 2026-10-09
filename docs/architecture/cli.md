# CLI Interface

Stargazer does not ship a custom terminal UI. CLI users connect to the MCP server via Claude Code or OpenCode.

The MCP server (`stargazer`) is the single interface between any frontend and the Python backend. Building a custom TUI would duplicate what battle-tested tools already provide — streaming, tool call rendering, input handling — with no domain-specific value.

## Supported Clients

Any MCP host that supports stdio or streamable HTTP transport:

| Client | Transport | Notes |
|--------|-----------|-------|
| Claude Code | stdio | `stargazer` as an MCP server in the project's `.mcp.json` |
| OpenCode | stdio | `stargazer` as a local MCP server in its config |

## Setup

For stdio, the client spawns `stargazer` as a subprocess and communicates over stdin/stdout; for remote access, `stargazer --http` exposes the same server over streamable HTTP. Install and client configuration are in [Using the MCP Server](../guides/mcp-server.md).

## Flyte CLI

All Stargazer tasks and workflows are standard Flyte v2 entities and can be managed directly through the Flyte CLI without the MCP server — registering, running, and inspecting tasks and workflows, plus a local TUI (`flyte start tui`) for browsing and launching them interactively. See the [Flyte CLI reference](https://www.union.ai/docs/v2/flyte/api-reference/flyte-cli/) for the full command set.

## What Users Get

Regardless of client, users have the storage tools, the bundle tools, discovery of every registered task and workflow through `list_tasks`, their execution through `run_task` and `run_workflow`, and the `stargazer://config` resource. The MCP server handles discovery and type serialization; the client handles LLM interaction and rendering.
