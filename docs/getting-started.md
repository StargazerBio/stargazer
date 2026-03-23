# Getting Started

## Quickstart

```bash
docker run -it ghcr.io/stargazerbio/stargazer
```

The container starts the MCP server over stdio. Connect your MCP client, then ask it to:

1. "Download the scrna_demo bundle"
2. "Run the scrna workflow"

## Client Configuration

Point your MCP client at the Docker image:

**Claude Code** — add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "stargazer": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/stargazerbio/stargazer"]
    }
  }
}
```

**OpenCode / Cursor** — same `command` + `args` pattern in your client's MCP config.

## Configuration

Pass environment variables with `-e` to control storage behavior:

| Setup | What to set |
|-------|-------------|
| **Default** — local cache + public IPFS gateway | Nothing |
| **Pinata (public)** — uploads to public network | `PINATA_JWT`, `PINATA_VISIBILITY=public` |
| **Pinata (private)** — uploads to private network | `PINATA_JWT` |

```bash
docker run -i --rm -e PINATA_JWT=your_jwt ghcr.io/stargazerbio/stargazer
```

See [Configuration](architecture/configuration.md) for details.

## Exploring Directly

To drop into a shell instead of starting the MCP server:

```bash
docker run -it --entrypoint bash ghcr.io/stargazerbio/stargazer
```

From there you can run workflows directly or use the [Flyte TUI](https://www.union.ai/docs/v2/flyte/user-guide/running-locally/#terminal-ui).

## Installing from Source

For development or contributing:

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/)

```bash
git clone <repo-url>
cd stargazer
uv pip install -e .
stargazer
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "stargazer": {
      "command": "stargazer",
      "args": []
    }
  }
}
```

## Docs

To preview documentation locally:

```bash
uv run python docs/gen_catalog.py
uv run zensical serve
```
