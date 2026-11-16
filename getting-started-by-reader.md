---
title: getting-started-by-reader
status: review
priority: normal
created: 2026-11-16
pr: 151
---

The docs' first pages serve several readers at once, and the main one, a researcher who knows notebooks and little else, has the most to wade through (read 2026-11-16):

- `docs/getting-started.md` carries the researcher's path (sign in or `docker run`, open a tutorial, bring a file) on the same page as the script header's pixi tables, MCP client configuration, a source install and the docs preview.
- `docs/architecture/overview.md` opens with a four-layer diagram whose top layer is the MCP server, while the page's own Interface section and every other doc say the notebook is the primary surface.

## Plan

- [x] Getting Started is the researcher's page: Hosted, Run It Locally, Use Your Own Files, then where to go next (the four tutorials in order). One screen each.
- [x] Packages and Tools moves beside Where Your Code Runs, which already owns headers. Agents gets its own guide, or joins Using the MCP Server. Installing from Source and the docs preview go to Contributing.
- [x] The overview's diagram puts notebooks and the SDK on top, with the MCP server as one of the surfaces.
- [x] `zensical.toml`'s nav for any page added, and a check for inbound anchors to the sections that move (`grep -rn "getting-started.md#" docs runtime src`).

## Choices

- Agents get their own guide, Agents in the Notebook.
- Getting Started's storage table is dropped for a link to Configuration's environment variables.

## Verification recipe

From the worktree: `pixi run zensical build --clean` reports no issues; every `docs/**/*.md` appears in `zensical.toml`'s nav; every relative link and anchor in the touched pages resolves against `site/`; `pixi run zensical serve` and read Getting Started (four sections in its table of contents) and the overview diagram (Surfaces on top, notebooks first). All passed for PR 151.

The README is out of scope: it's the user's.

Related: [[board]], [[frontend-polish]].
