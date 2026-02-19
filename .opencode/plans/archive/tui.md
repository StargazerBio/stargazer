# TUI Implementation Plan — Superseded

## Status: Cancelled

This plan has been replaced by the "Bring Your Own TUI" approach. See `.opencode/specs/tui.md` for the current strategy.

## Decision Summary

Instead of building a custom Ink/React TUI compiled via Bun, CLI users connect to the Stargazer MCP server using their preferred MCP-compatible client (Claude Code, OpenCode, Claude Desktop, etc.).

**Rationale:**
- A custom TUI would duplicate streaming, tool rendering, and input handling that existing clients already provide
- The `frontend/core/` shared TypeScript library is no longer needed (browser uses Chainlit, not a shared React core)
- Maintenance cost of a second language (TypeScript) and build pipeline (Bun) is not justified
- The MCP server is the correct abstraction boundary — invest there instead

## What Was Planned (for reference)

The original plan called for:
- `frontend/core/` — shared TypeScript library (MCP client, chat engine, React hooks)
- `frontend/tui/` — Ink-based terminal chat app
- Bun-compiled single binary
- 7 implementation phases

None of this will be built. The MCP server plan (`mcp_server.md`) remains the active plan for CLI-facing work.
