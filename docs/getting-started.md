# Getting Started

Stargazer ships two Docker images for different workflows:

- **`stargazer:note`** — if you want to run pipelines, explore data, and visualize results in a notebook
- **`stargazer:chat`** — if you want to build new tasks and workflows with an agentic dev harness

## Note — Notebook Interface

```bash
docker run -p 8080:8080 ghcr.io/stargazerbio/stargazer:note
```

Opens a [Marimo](https://marimo.io/) notebook at `http://localhost:8080` in edit mode. From there you can import stargazer tasks, run workflows, and visualize results interactively. This is the same image used in production.

## Chat — Dev Harness

```bash
docker run -it -v $(pwd):/stargazer ghcr.io/stargazerbio/stargazer:chat
```

Mount your local clone into the container. The entrypoint syncs dependencies and drops you into a shell with Claude Code, OpenCode, and standard dev tooling. See [Contributing](guides/contributing.md) for the full dev setup.

## MCP Client Configuration

Both images include the MCP server. Point your MCP client at the Docker image:

**Claude Code** — add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "stargazer": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/stargazerbio/stargazer:note"]
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
docker run -p 8080:8080 -e PINATA_JWT=your_jwt ghcr.io/stargazerbio/stargazer:note
```

See [Configuration](architecture/configuration.md) for details.

## Installing from Source

**Prerequisites:** Python 3.13+, [uv](https://docs.astral.sh/uv/)

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
