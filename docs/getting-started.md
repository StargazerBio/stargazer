# Getting Started

Stargazer installs as a Python package (`stargazer-bio`), and each release publishes one end-user Docker image, **`stargazer`**, for running pipelines and exploring data in a notebook with an AI agent alongside.

If you want to add tasks or workflows to Stargazer itself, see [Contributing](guides/contributing.md) for the native setup. The image below is for using Stargazer, not editing it.

## Notebook Interface

```bash
docker run -p 8080:8080 ghcr.io/stargazerbio/stargazer
```

Serves [Marimo](https://marimo.io/) notebooks at `http://localhost:8080` in edit mode, opening on the Assets tutorial. The rest are in the file explorer, in a `notebooks/` folder: `tutorials/`, in reading order Assets, Tasks, Workflows and Execution, `workflows/`, and `templates/` with `blank.py` and `basic.py` to start your own from. Start a notebook of your own by copying a template rather than with marimo's *Create a new notebook*, whose notebooks don't have Stargazer installed. This is the image hosted notebooks run on (see [Notebooks](architecture/notebook.md) and [Notebook Runtime](architecture/runtime.md)).

## Use Your Own Files

Mount a directory at `/workspace`, the notebook's working directory:

```bash
docker run -p 8080:8080 -v "$PWD/data":/workspace ghcr.io/stargazerbio/stargazer
```

Its files show up in the notebook's file explorer and its terminal, so a notebook reads them by relative path (`pd.read_csv("reads/sample.csv")`). The `notebooks/` folder is copied there at start, skipping files the directory already has, so your edits are kept. On Linux the container runs as user 1000, so the directory must be writable by that user.

To keep assets between runs, mount a volume at `/home/flyte/.stargazer`, which holds the asset store, its index and the download cache:

```bash
docker run -p 8080:8080 -v stargazer-data:/home/flyte/.stargazer ghcr.io/stargazerbio/stargazer
```

A file in `/workspace` isn't an asset until a notebook stores it with `await asset.update(path, ...)`; after that `assemble()` finds it by its metadata and `fetch()` copies it into the download cache. The Assets tutorial walks through it. To keep assets somewhere else, set `STARGAZER_STORE_ROOT` and `STARGAZER_INDEX_URL` (see Configuration below).

## Agent — Claude Code in the Notebook

Press ++ctrl+grave++ in the notebook to open its terminal, and run `claude` once to sign in. Then open the AI panel from the sidebar, switch to **Agents** and start a new Claude session. Claude Code works in the notebook's working directory, with the Stargazer SDK installed at `/stargazer` and the tools the bundled workflows call (GATK, samtools, BWA) on the `PATH`, so it can run them for you. When it edits the open notebook, the changed cells show up in the editor, ready to run. The terminal and the agent are part of the editor, so a notebook opened to run has neither.

## MCP Client Configuration

The MCP server runs from a source install with the `mcp` extra. Point your MCP client (Claude Code, OpenCode, Cursor) at the `stargazer` command; the config is in [Using the MCP Server](guides/mcp-server.md#connecting-a-client).

## Configuration

Set environment variables to control storage behavior (with `-e` for a container):

| Setup | What to set |
|-------|-------------|
| **Default** — your files stored under `~/.stargazer` (inside the container, for an image), public datasets fetched by CID | Nothing |
| **Shared public data** — search public datasets by metadata | `PINATA_JWT` |
| **Your own storage location** — keep files elsewhere, or in a bucket | `STARGAZER_STORE_ROOT`, `STARGAZER_INDEX_URL` |

```bash
docker run -p 8080:8080 -e PINATA_JWT=your_jwt ghcr.io/stargazerbio/stargazer:latest
```

See [Configuration](architecture/configuration.md) for details.

## Installing from Source

**Prerequisites:** Python 3.14+, [uv](https://docs.astral.sh/uv/)

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
