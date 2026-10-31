---
title: marimo-terminal
status: doing
priority: normal
created: 2026-10-28
---

The notebook pod's terminal and its agent become marimo's own instead of what
the proxy builds. marimo's editor has a terminal in its developer panel
(Ctrl-` opens it) and, behind its `external_agents` Lab flag, an agent panel
that talks the Agent Client Protocol to Claude Code through
`@agentclientprotocol/claude-agent-acp`, or OpenCode (`opencode acp`). The overlay terminal the proxy splices
into every page duplicates the first, and running `claude` in it is a weaker
version of the second.

What we give up: a terminal and an agent in run mode. marimo's terminal closes
with "Terminal only available in edit mode", and the agent panel is part of the
editor. The overlay's scrubbing of secret-shaped env vars from the shell goes
too, since marimo's terminal inherits marimo's env; that was tidiness, not a
boundary. The agent keeps the scrubbed env.

## The one piece of glue

marimo's agent panel dials `ws(s)://<page host>:<port>/message`, a port per
agent fixed in its frontend (Claude 3017, OpenCode 3023; checked in
0.25.1/0.25.2), and its docs start each agent with `npx stdio-to-ws ...`. Neither works in a hosted pod: Union serves
the app's one port at 443, and `stdio-to-ws` binds every interface with no
auth, which would let any pod in the cluster drive the user's Claude Code. So
the proxy keeps two small pieces: a script spliced into each page that points
those URLs at `/__sg__/agent/<name>` on the page's own origin, and that
websocket, which runs the agent per connection over stdio, line-framed the way
`stdio-to-ws` does, behind the sign-in gate like every route. marimo sends
each message as a binary frame.

## Sign-ins persist

A sign-in made in one pod is there in the next. The proxy keeps a fixed list
of files from the home directory (Claude Code's `~/.claude/.credentials.json`
and `~/.claude.json`, OpenCode's `~/.local/share/opencode/auth.json`) under
`users/<subject>/agents/` in the workspace store, beside the workspace rather
than in it: restored at launch with mode 600, saved by the same passes and the
shutdown flush, deleted from the store on a sign-out. The per-user role
already covers `users/<subject>/` (infra `aws/storage.tf`), so infra needs no
change. The bucket is versioned with 30-day noncurrent expiry, so an old token
lingers that long after a sign-out.

## Pieces

- [x] Proxy: drop `term_proxy` (`/__sg__/term`), `_set_winsize` and the
      overlay's injection; add `/__sg__/agent/<name>` and the redirect script. The
      save banner's injection stays. Drop `runtime/terminal_overlay.html`.
- [x] The image: Node 22, `claude-agent-acp` and `opencode-ai`, pinned; `claude` on PATH is
      the binary the agent SDK ships, so login and agent share one version;
      marimo 0.25.1 (0.23.6 names the old `claude-code-acp` package); a
      user `marimo.toml` turning `external_agents` on.
- [x] Launch: `marimo edit --watch`, so the agent's edits to the open
      notebook reach the editor (marked stale, marimo's default).
- [x] `runtime/notebook_agent.md`: it's read by the agent in the panel; the
      file-reload caveat changes with `--watch`.
- [x] Tests: `tests/unit/test_proxy.py` and `tests/unit/test_dockerfile.py`.
- [x] Docs: `docs/architecture/notebook.md`, `docs/architecture/overview.md`,
      `docs/architecture/runtime.md`, `docs/getting-started.md`,
      `docs/index.md`, the runtime internals reference, and
      `runtime/launch-notebook.sh`'s header. Check `runtime/save_banner.html`.

- [x] Sign-ins persist in the store.
- [ ] A real agent turn locally, with a sign-in.
- [ ] Union, as the test account: both agents connect, a sign-in survives a
      restart, and `/__sg__/agent/<name>` without a token is refused.

## Verification so far

- Unit tier: 289 passed.
- Local image (`docker build -f runtime/Dockerfile`), in the browser: Claude
  and OpenCode sessions both reach "Agent is connected" through the proxy;
  marimo's terminal opens in `/workspace` with `claude` 2.1.312, `opencode`,
  `claude-agent-acp`, `node` and `AGENTS.md`.
- Two containers sharing a local store (`STARGAZER_WORKSPACE_ROOT=/store`):
  sign-in files written in the first were saved under `agents/` (and
  `~/.claude/history.jsonl` wasn't); the second restored them at mode 600 and
  `opencode auth list` showed the credential; deleting Claude's credentials
  in it deleted them from the store.

## Elsewhere

- infra's `app/templates/_assets.html` mentions the overlay.
- The README's line on opening the terminal with Ctrl+` stays true, since
  marimo uses the same key; its "claude code or opencode" now means the panel.
