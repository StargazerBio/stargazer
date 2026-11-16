---
title: getting-started-by-reader
status: backlog
priority: normal
created: 2026-11-16
---

The docs' first pages serve several readers at once, and the main one, a researcher who knows notebooks and little else, has the most to wade through (read 2026-11-16):

- `docs/getting-started.md` carries the researcher's path (sign in or `docker run`, open a tutorial, bring a file) on the same page as the script header's pixi tables, MCP client configuration, a source install and the docs preview.
- `docs/architecture/overview.md` opens with a four-layer diagram whose top layer is the MCP server, while the page's own Interface section and every other doc say the notebook is the primary surface.

## Plan

- [ ] Getting Started is the researcher's page: Hosted, Run It Locally, Use Your Own Files, then where to go next (the four tutorials in order). One screen each.
- [ ] Packages and Tools moves beside Where Your Code Runs, which already owns headers. Agents gets its own guide, or joins Using the MCP Server. Installing from Source and the docs preview go to Contributing.
- [ ] The overview's diagram puts notebooks and the SDK on top, with the MCP server as one of the surfaces.
- [ ] `zensical.toml`'s nav for any page added, and a check for inbound anchors to the sections that move (`grep -rn "getting-started.md#" docs runtime src`).

The README is out of scope: it's the user's.

Related: [[board]], [[frontend-polish]].
