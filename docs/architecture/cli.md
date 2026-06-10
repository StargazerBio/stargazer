# CLI Interface

Stargazer does not ship a custom terminal UI. CLI users connect to the MCP server via Claude Code or OpenCode.

The MCP server (`stargazer serve`) is the single interface between any frontend and the Python backend. Building a custom TUI would duplicate what battle-tested tools already provide — streaming, tool call rendering, input handling — with no domain-specific value.

## Supported Clients

Any MCP host that supports stdio or streamable HTTP transport:

| Client | Transport | Notes |
|--------|-----------|-------|
| Claude Code | stdio | `stargazer serve` as MCP server in project config |
| OpenCode | stdio | Configure in `.opencode/` |

## Setup

For stdio, the client spawns `stargazer serve` as a subprocess and communicates over stdin/stdout; for remote access, `stargazer serve --http --port 8080` exposes the same server over streamable HTTP. Client configuration examples are in [Using the MCP Server](../guides/mcp-server.md).

## Flyte CLI

All Stargazer tasks and workflows are standard Flyte v2 entities and can be managed directly through the Flyte CLI without the MCP server — registering, running, and inspecting tasks and workflows, plus a local TUI (`flyte start tui`) for browsing and launching them interactively. See the [Flyte CLI reference](https://www.union.ai/docs/v2/flyte/api-reference/flyte-cli/) for the full command set.

## What Users Get

Regardless of client, users have access to all bioinformatics task tools, composite workflow tools, resources for context, prompt templates, and mode-aware tool registration. The MCP server handles mode detection, type serialization, and tool registration. The client handles LLM interaction and rendering.
