---
title: skills-replace-mcp
status: maybe
priority: normal
created: 2026-10-28
---

Agents working with Stargazer get what they need from skills and the SDK,
not from the `stargazer` MCP server, and the user-facing agent context is
consolidated into one set of skills that ships with the notebook image.

## Why the MCP server doesn't earn its place

Since ticket [[agent-mcp]], the notebook pod's agent panel has the server's
tools, so the first two points below no longer hold.

- **marimo can't use it.** marimo's chat panel takes MCP servers only from
  its presets (`[mcp] presets = ["marimo", "context7"]`); its docs say custom
  servers aren't supported yet (docs.marimo.io, read 2026-10-28).
- **The notebook pod doesn't use it.** The agent there is Claude Code in a
  terminal, started in `/workspace` with `/workspace/AGENTS.md`
  (`runtime/notebook_agent.md`). The notebook image doesn't configure the server;
  only a checkout's `.mcp.json` does.
- **Its tools are thin wrappers over the SDK**: `query_files`,
  `upload_file`, `download_file`, `update_file`, `delete_file`,
  `publish_file`, `list_bundles`, `fetch_resource_bundle`, `list_tasks`,
  `run_task`, `run_workflow` and the `stargazer://config` resource. An agent
  with a shell writes the same calls as Python, which is also what a
  notebook needs in the end.

## Plan

- [ ] **Decide the skill set.** What the user's agent needs that
      `runtime/notebook_agent.md` holds today (where it is, marimo conventions,
      tasks, assets, workflows, local vs remote runs), split into skills
      that load on demand, with `AGENTS.md` left as the short always-loaded
      part. Consider marimo's official skills (`marimo-team/skills`) and
      `marimo pair`, which gives the agent the live notebook (run cells,
      read variables) instead of only the file.
- [ ] **Ship them in the notebook image**, where Claude Code in
      `/workspace` finds them. Check how they interact with the workspace's
      hydrate and save, as `/workspace/AGENTS.md` already does (a baked copy
      isn't saved until edited; an edited one wins at the next launch).
- [ ] **Remove the MCP server**: `src/stargazer/server.py`,
      `src/stargazer/marshal.py`, the `mcp` extra, the `stargazer` script,
      `.mcp.json`, `docs/architecture/mcp-server.md` and its nav entry, and
      their tests. `stargazer.registry` stays: the scRNA notebook lists tasks
      with `TaskRegistry().to_catalog()`.
- [ ] **AGENTS.md and docs** stop describing the MCP server as a surface.

## Open questions

- Whether "consolidate" also folds the repo's maintainer skills
  (`.claude/skills/`) into the user set, or the two stay apart: maintainer
  skills are about changing Stargazer, user skills about using it.
- Where user skills live in the repo, so the image and a checkout share one
  copy.

Related: [[board]].
