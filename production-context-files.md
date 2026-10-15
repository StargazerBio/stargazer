---
title: Condensed context files for production use (separate from dev)
status: backlog
priority: normal
created: 2026-05-19
---

An agent launched from a notebook's terminal overlay opens in the workspace
directory (`app/launch-notebook.sh`), and no context file ships there; the
only condensed copy of the authoring conventions is `marimo.toml`'s `[ai]`
rules (ticket `marimo-toml`).
