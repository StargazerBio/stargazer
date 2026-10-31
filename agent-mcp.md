---
title: agent-mcp
status: done
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
On Union as the test account, from a workspace notebook's panel, OpenCode's
`query_files` read the user's index, and `run_task samtools_faidx` started
a `build-image` run and `gatk.samtools_faidx` (`us2xfskxpdkvj4vmmj9l`), both
SUCCEEDED in `u-pryce`. The agent got "Request timed out", because OpenCode
gives up on an MCP request after a minute. The image's `opencode.jsonc` now
sets `experimental.mcp_timeout` to an hour: a 1 ms override made a local
call fail and the image's config made it pass. On the re-launched pod,
`run_workflow prepare_reference` (`u2nx6prsxzwf24drkcqk`) returned its
`Reference` to the agent, but in under a minute. Not driven: a call over a
minute on Union with the fix, and a Claude turn (needs a sign-in).

## Verification recipe

1. `docker build -f runtime/Dockerfile -t stargazer:agent-mcp .`
2. `docker run -d --name sg -p 8091:8080 stargazer:agent-mcp`
3. `docker exec sg curl -s localhost:8000/mcp ...` initialize and
   `tools/list` return the server's tools.
4. Through `ws://localhost:8091/__sg__/agent/<name>`, send `initialize` and a
   `session/new` with `mcpServers: []`, as marimo does: each agent reports
   the `stargazer` server connected (OpenCode's `opencode mcp list`, Claude
   Code's MCP status), without a sign-in where it can.
5. To check OpenCode's timeout, mount an `opencode.jsonc` with
   `{"experimental": {"mcp_timeout": 1}}` over
   `/home/flyte/.config/opencode/opencode.jsonc`: a tool call fails.
6. `docker rm -f sg`.

On Union: push `ghcr.io/stargazerbio/debug:<tag>` (a new tag per push, since a
node may keep an old pull), redeploy the test dashboard with
`STARGAZER_NOTEBOOK_IMAGE`, open a workspace notebook in edit mode, start an
OpenCode session (its free model needs no sign-in) and ask for a
`run_task`; watch `union_dashboard.py check <app>` for the run. Tear down
with `union_dashboard.py teardown`.

## Outcome

Shipped in StargazerBio/stargazer#115 (`f0904cd`), merged 2026-10-31. The
image runs the `stargazer` MCP server beside marimo in edit mode, and the
agent bridge adds it to every panel session. Verified locally (all 11 tools,
OpenCode calling them through the bridge) and on Union as the test account
(`run_task samtools_faidx` and `run_workflow prepare_reference` from a
workspace notebook's OpenCode). Left: a tool call over a minute on Union with
the `mcp_timeout` fix, and a Claude Code turn, which needs a sign-in. The PR
had no review comments.
