---
title: agent-mcp
status: review
priority: normal
created: 2026-10-30
pr: 115
---

The agents in a notebook's agent panel (Claude Code and OpenCode) get the
`stargazer` MCP server's tools: `list_tasks`, `run_task`, `run_workflow`,
`query_files` and the rest, against the pod's own store, index and Flyte
project.

marimo creates every agent session with `mcpServers: []` (its 0.25.1 panel
bundle), so the pod supplies the server itself. Both pinned agents advertise
HTTP MCP (`mcpCapabilities.http`) and map ACP's `mcpServers` entries into
their own config.

## Plan

- [x] **The server runs beside marimo.** The image builds the SDK with the
      `mcp` extra into its own venv from `uv.lock`, editable from
      `/stargazer` so `init_flyte()` bundles runs from the same tree the
      notebooks do. In edit mode the launch script starts `stargazer --http`
      on loopback with the pod's whole env: the agents' env has no project
      key (`_agent_env()` strips `_UNION_EAGER_API_KEY`), so a server they
      spawned couldn't start runs.
- [x] **The bridge adds it to each session.** Every panel request that
      carries `mcpServers` (`session/new`, `session/load`, `session/resume`,
      `session/fork`) gets the server's HTTP entry appended before it reaches
      the agent.
- [x] **Docs and the pod's AGENTS.md** say the tools are there and when to
      use them.

## Verification

Locally, on `stargazer:agent-mcp`: the server answered `tools/list` with
all 11 tools (~133 MB RSS), and a `run`-mode pod had nothing on 8000.
Through the bridge, OpenCode's `session/new` connected to the server, and
with its free default model it called `stargazer_list_tasks` (the SDK's
workflows came back) and `stargazer_query_files`. A signed-out Claude Code
`session/new` made five requests to the server, but a prompt needs a sign-in.
Not driven: Union (the server reaching the owner's project with the project
key) and a Claude turn that calls a tool.

## Verification recipe

1. `docker build -f runtime/Dockerfile -t stargazer:agent-mcp .`
2. `docker run -d --name sg -p 8091:8080 stargazer:agent-mcp`
3. `docker exec sg curl -s localhost:8000/mcp ...` initialize and
   `tools/list` return the server's tools.
4. Through `ws://localhost:8091/__sg__/agent/<name>`, send `initialize` and a
   `session/new` with `mcpServers: []`, as marimo does: each agent reports
   the `stargazer` server connected (OpenCode's `opencode mcp list`, Claude
   Code's MCP status), without a sign-in where it can.
5. `docker rm -f sg`.
