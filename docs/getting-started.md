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

## Configuration

Stargazer's storage behavior is controlled by two environment variables:

| Setup | Storage | Downloads | What to set |
|-------|---------|-----------|-------------|
| **Default** | Local filesystem | Cache + public IPFS gateway | Nothing |
| **Pinata (public)** | Pinata (public network) | Cache + public or private IPFS gateway | `PINATA_JWT`, `PINATA_VISIBILITY=public` |
| **Pinata (private)** | Pinata (private network) | Cache + signed URLs | `PINATA_JWT` |

See [Configuration](architecture/configuration.md) for details.

## Docs

To preview the documentation locally:

```bash
uv run python docs/gen_catalog.py  # generate dynamic content
uv run zensical serve              # start the dev server at 0.0.0.0:8001
```

Or to build a static site:

```bash
uv run python docs/gen_catalog.py
uv run zensical build
```

## First Workflow

Once your client is connected to the MCP server, you can run a workflow by asking your LLM to execute it. The server exposes all available tasks and workflows as tools — your client discovers them automatically via MCP.
