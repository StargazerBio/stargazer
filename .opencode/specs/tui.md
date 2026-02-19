# CLI Interface — Bring Your Own TUI

## Design Decision

Stargazer does not ship a custom terminal UI. CLI users connect to the Stargazer MCP server using whichever MCP-compatible client they prefer.

The MCP server (`stargazer serve`) is the single interface between any frontend and the Python backend. Building a custom TUI would duplicate what battle-tested tools already provide — streaming, tool call rendering, input handling, keybindings — with significant ongoing maintenance cost and no domain-specific value add.

## Supported Clients

Any MCP host that supports stdio or streamable HTTP transport can consume Stargazer's tools, resources, and prompts. Known-compatible clients:

| Client | Transport | Notes |
|--------|-----------|-------|
| Claude Code | stdio | `stargazer serve` as MCP server in project config |
| OpenCode | stdio | Configure in `.opencode/` |
| Claude Desktop | stdio | Add to `claude_desktop_config.json` |
| Cursor / Windsurf | stdio | IDE MCP server configuration |
| MCP Inspector | stdio | Development and debugging |

## Setup

### stdio (most clients)

The client spawns `stargazer serve` as a subprocess and communicates over stdin/stdout.

Example Claude Desktop configuration:

```json
{
  "mcpServers": {
    "stargazer": {
      "command": "stargazer",
      "args": ["serve"]
    }
  }
}
```

### Streamable HTTP (remote access)

For clients that support HTTP transport, or when the MCP server runs on a different machine:

```bash
stargazer serve --http --port 8080
```

## What Users Get

Regardless of which client they use, users have access to:

- All bioinformatics task tools (bwa_mem, mark_duplicates, etc.)
- Composite workflow tools (germline_cohort, preprocess_sample, etc.)
- Resources for context (stargazer://references, stargazer://samples, etc.)
- Prompt templates for common workflows (align_reads, call_variants, etc.)
- Mode-aware tool registration (local vs cloud)

The MCP server handles mode detection, type serialization, and tool registration. The client handles LLM interaction and rendering.

## Relationship to Browser

The browser interface (Chainlit) is the only Stargazer-maintained frontend. It exists because browser users need a hosted experience with a provided LLM — a requirement that MCP clients can't fulfill. CLI users who bring their own LLM API key and run locally have no such need.
