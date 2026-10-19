# Getting Started

Stargazer installs as a Python package, and the repository's `Dockerfile` builds one end-user Docker image, **`stargazer-note`**, for running pipelines and exploring data in a notebook with an AI agent alongside.

If you want to add tasks or workflows to Stargazer itself, see [Contributing](guides/contributing.md) for the native setup. The image below is for using Stargazer, not editing it.

## Notebook Interface

```bash
docker run -p 8080:8080 ghcr.io/stargazerbio/stargazer-note
```

Opens the Assets tutorial, a [Marimo](https://marimo.io/) notebook, at `http://localhost:8080` in edit mode. From there you can import stargazer tasks, run workflows, and visualize results interactively. The published tag can lag the source; [Contributing → Building Images](guides/contributing.md#building-images) builds it from a checkout under the same name. It is the image hosted notebooks run on (see [Notebooks](architecture/notebook.md) for the notebook types and [App](architecture/app.md) for hosting).

## Agent — Claude Code in the Notebook

Press Ctrl+` in the notebook to drop down a terminal, and run `claude` to log in and start Claude Code. It opens in the notebook's working directory, with the Stargazer SDK installed at `/stargazer` and the tools the bundled workflows call (GATK, samtools, BWA) on the `PATH`, so the agent can run them for you.

## MCP Client Configuration

The MCP server runs from a source install with the `mcp` extra. Point your MCP client at the `stargazer` command:

**Claude Code** — add to `.mcp.json`:

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

**OpenCode / Cursor** — same `command` + `args` pattern in your client's MCP config. More in [Using the MCP Server](guides/mcp-server.md).

## Configuration

Set environment variables to control storage behavior (with `-e` for a container):

| Setup | What to set |
|-------|-------------|
| **Default** — your files stored under `~/.stargazer` (inside the container, for an image), public datasets fetched by CID | Nothing |
| **Shared public data** — search public datasets by metadata | `PINATA_JWT` |
| **Your own storage location** — keep files elsewhere, or in a bucket | `STARGAZER_STORE_ROOT`, `STARGAZER_INDEX_URL` |

```bash
docker run -p 8080:8080 -e PINATA_JWT=your_jwt ghcr.io/stargazerbio/stargazer-note:latest
```

See [Configuration](architecture/configuration.md) for details.

## Installing from Source

**Prerequisites:** Python 3.13+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/StargazerBio/stargazer.git
cd stargazer
uv pip install -e ".[mcp]"
stargazer
```

`stargazer` serves MCP over stdio; add the `bio` extra to run the scRNA-seq tasks locally, and `notebook` for the notebooks.

## Docs

To preview documentation locally:

```bash
uv run python docs/gen_catalog.py
uv run zensical serve
```
