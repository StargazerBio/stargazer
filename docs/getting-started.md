# Getting Started

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for package management
- An MCP-compatible client (Claude Code, OpenCode, Cursor, etc.)

## Installation

```bash
git clone <repo-url>
cd stargazer
uv pip install -e .
```

## Running the MCP Server

```bash
stargazer serve
```

This starts the MCP server over stdio. Your client spawns it as a subprocess.

### Client Configuration

**Claude Code / OpenCode** — add to your MCP server config:

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

**Remote access** — use HTTP transport:

```bash
stargazer serve --http --port 8080
```

## Modes

Stargazer's behavior is controlled by a single environment variable:

| Mode | Storage | Execution | Setup |
|------|---------|-----------|-------|
| **Local** (default) | Filesystem | Flyte local | Nothing |
| **Local + Pinata** | IPFS via Pinata | Flyte local | Set `PINATA_JWT` |
| **Cloud** | IPFS via Pinata | Flyte remote (Union) | Set `STARGAZER_MODE=cloud`, `PINATA_JWT` |

See [Modes](architecture/modes.md) for details.

## First Workflow

Once your client is connected to the MCP server, you can run a workflow by asking your LLM to execute it. The server exposes all available tasks and workflows as tools — your client discovers them automatically via MCP.
