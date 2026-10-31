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
`@agentclientprotocol/claude-agent-acp`. The overlay terminal the proxy splices
into every page duplicates the first, and running `claude` in it is a weaker
version of the second.

What we give up: a terminal and an agent in run mode. marimo's terminal closes
with "Terminal only available in edit mode", and the agent panel is part of the
editor. The overlay's scrubbing of secret-shaped env vars from the shell goes
too, since marimo's terminal inherits marimo's env; that was tidiness, not a
boundary. The agent keeps the scrubbed env.

## The one piece of glue

marimo's agent panel dials `ws(s)://<page host>:3017/message`, a port fixed in
its frontend (checked in 0.25.1/0.25.2), and its docs start the agent with
`npx stdio-to-ws ... --port 3017`. Neither works in a hosted pod: Union serves
the app's one port at 443, and `stdio-to-ws` binds every interface with no
auth, which would let any pod in the cluster drive the user's Claude Code. So
the proxy keeps two small pieces: a script spliced into each page that points
that one URL at `/__sg__/agent` on the page's own origin, and that websocket,
which runs `claude-agent-acp` per connection over stdio, line-framed the way
`stdio-to-ws` does, behind the sign-in gate like every route.

## Pieces

- [ ] Proxy: drop `term_proxy` (`/__sg__/term`), `_set_winsize` and the
      overlay's injection; add `/__sg__/agent` and the redirect script. The
      save banner's injection stays. Drop `runtime/terminal_overlay.html`.
- [ ] The image: Node 22 and `claude-agent-acp`, pinned; `claude` on PATH is
      the binary the agent SDK ships, so login and agent share one version;
      marimo 0.25.1 (0.23.6 names the old `claude-code-acp` package); a
      user `marimo.toml` turning `external_agents` on.
- [ ] Launch: `marimo edit --watch`, so the agent's edits to the open
      notebook reach the editor (marked stale, marimo's default).
- [ ] `runtime/notebook_agent.md`: it's read by the agent in the panel; the
      file-reload caveat changes with `--watch`.
- [ ] Tests: `tests/unit/test_proxy.py` and `tests/unit/test_dockerfile.py`.
- [ ] Docs: `docs/architecture/notebook.md`, `docs/architecture/overview.md`,
      `docs/architecture/runtime.md`, `docs/getting-started.md`,
      `docs/index.md`, the runtime internals reference, and
      `runtime/launch-notebook.sh`'s header. Check `runtime/save_banner.html`.

## Elsewhere

- infra's `app/templates/_assets.html` mentions the overlay.
- The README's line on opening the terminal with Ctrl+` stays true, since
  marimo uses the same key; its "claude code or opencode" now means the panel.
