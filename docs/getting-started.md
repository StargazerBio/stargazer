# Getting Started

Stargazer ships two end-user Docker images:

- **`stargazer-note`** — for running pipelines and exploring data in a notebook
- **`stargazer-chat`** — for driving Stargazer through a pre-wired AI agent (Claude Code + OpenCode + MCP server)

If you want to add tasks or workflows to Stargazer itself, see [Contributing](guides/contributing.md) for the native setup. The two images below are for using Stargazer, not editing it.

## Note — Notebook Interface

```bash
docker run -p 8080:8080 ghcr.io/stargazerbio/stargazer-note:latest
```

Opens a [Marimo](https://marimo.io/) notebook at `http://localhost:8080` in edit mode. From there you can import stargazer tasks, run workflows, and visualize results interactively. This is the same image used in production.

## Chat — Agentic Interface

```bash
docker run -it ghcr.io/stargazerbio/stargazer-chat:latest
```

Drops you into a shell with Claude Code and OpenCode pre-wired against the Stargazer MCP server. Ask the agent to list tasks, run a workflow, query stored files — it dispatches via MCP. The image carries the runtime deps for the scrna pipeline, so the agent can run that workflow locally; heavier pipelines (gatk, alignment) dispatch to whatever backend `.flyte/config.yaml` points at.

## MCP Client Configuration

Both images include the MCP server. Point your MCP client at the Docker image:

**Claude Code** — add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "stargazer": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/stargazerbio/stargazer-note:latest"]
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
docker run -p 8080:8080 -e PINATA_JWT=your_jwt ghcr.io/stargazerbio/stargazer-note:latest
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
