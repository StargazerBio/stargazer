---
title: marimo's terminal replaces the terminal overlay
status: maybe
priority: normal
created: 2026-10-28
---

The notebook pod's terminal, where Claude Code runs, becomes marimo's own
instead of the overlay the proxy splices into every page. marimo's editor has
a terminal in its developer panel (Cmd/Ctrl-J, or Ctrl-` to open it), so the
overlay duplicates it. The proxy otherwise stays as it is: the sign-in gate,
cookie stripping, workspace hydrate and save, the save banner, and the
`/__sg__/` routes other than the terminal.

What we give up: a terminal in run mode. marimo's terminal closes with
"Terminal only available in edit mode" (`_server/api/endpoints/terminal.py`,
checked in 0.23.6 and 0.25.1). The overlay's scrubbing of secret-shaped env
vars from the shell goes too; that was tidiness, not a boundary.

## Pieces

- [ ] Proxy: drop `term_proxy` (`/__sg__/term`), `_shell_env`,
      `_set_winsize`, and the overlay's injection; the save banner's
      injection stays. Drop `app/terminal_overlay.html`.
- [ ] Both images: the overlay file leaves `notebook_app_img_recipe`
      (`app/per_notebook.py`) and `Dockerfile`, and the `stargazer-image`
      workflow's paths.
- [ ] Tests: `tests/unit/test_proxy.py` and `tests/unit/test_dockerfile.py`.
- [ ] Docs: `docs/architecture/notebook.md`, `docs/architecture/overview.md`,
      `docs/getting-started.md`, `docs/guides/contributing.md`,
      `docs/index.md`, and `app/launch-notebook.sh`'s header. Check
      `app/save_banner.html` and `app/templates/_assets.html`, which mention
      an overlay.

## To check before relying on it (unmeasured)

- marimo's terminal opens in `/workspace`, so Claude Code there reads
  `/workspace/AGENTS.md`. The launch script `cd`s there before starting
  marimo, so it should.
- `claude` is on its PATH.
- Its websocket gets through the proxy's generic websocket forwarding and
  the sign-in gate on Union. marimo runs with `--no-token`, so marimo's own
  auth is off and the gate is the only check, as for every other route.

## Verification

- Local `stargazer` image: Ctrl-` opens marimo's terminal in `/workspace`,
  `claude` starts there and loads `AGENTS.md`.
- Union, as the test account: the same in an edit-mode notebook, and a
  request to the terminal's websocket without a token is refused.

## Elsewhere

The README's line on opening the terminal with Ctrl+` stays true, since
marimo uses the same key.
