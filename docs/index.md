# Stargazer

Stargazer is a bioinformatics pipeline framework built on [Flyte v2](https://flyte.org/). It provides a library of composable tasks for common bioinformatics operations and exposes them through an MCP server that any AI-powered client can consume.

## How It Works

1. **Assets** carry structured metadata that describes every file's role in the system — reference genomes, read pairs, alignments, variant calls
2. **Tasks** are atomic operations that fetch assets, run bioinformatics tools, and produce new assets
3. **Workflows** compose tasks into end-to-end pipelines (e.g., germline variant calling for a cohort)
4. **MCP server** exposes tasks, workflows, and storage as tools that LLM clients can invoke

## Interface

Stargazer is used through the MCP server — bring your own MCP-compatible client (Claude Code, OpenCode, Cursor, etc.) and connect to `stargazer serve`. Tasks and workflows can also be managed directly via the Flyte CLI.

## Documentation

- [Getting Started](getting-started.md) — go from zero to running your first workflow
- [Architecture](architecture/overview.md) — how the system is designed and why
- [Guides](guides/writing-a-task.md) — step-by-step walkthroughs for common tasks
- [API Reference](reference/api.md) — auto-generated from docstrings
