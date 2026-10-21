---
title: Notebooks on the devbox
status: backlog
priority: normal
created: 2026-10-08
---

The devbox dashboard and asset storage work (`cli/devbox_dashboard.py`, a stand-in user), and a tutorial launched in
run mode from that dashboard starts and serves marimo (2026-10-08). Edit
mode, workspace saving and the in-notebook terminal haven't been driven.

The devbox's notebook image comes from the local builder, which runs it as root: measured 2026-10-20 with flyte 2.10.7, a local build of `notebook_app_img_recipe` ends `USER root` (`HOME=/root`), while the Union-built image is `User=flyte`. The terminal agent's context file doesn't depend on it (it's `/workspace/AGENTS.md`, ticket `production-context-files`), but `/workspace` is chowned to `flyte`, so driving the terminal here should check which user the pod runs as.
