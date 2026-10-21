---
title: Notebooks on the devbox
status: done
priority: normal
created: 2026-10-08
pr: 73
---

The devbox dashboard and asset storage work (`cli/devbox_dashboard.py`, a stand-in user), and a tutorial launched in
run mode from that dashboard starts and serves marimo (2026-10-08). Edit
mode, workspace saving and the in-notebook terminal haven't been driven.

The devbox's notebook image comes from the local builder, which runs it as root: measured 2026-10-20 with flyte 2.10.7, a local build of `notebook_app_img_recipe` ends `USER root` (`HOME=/root`), while the Union-built image is `User=flyte`. The terminal agent's context file doesn't depend on it (it's `/workspace/AGENTS.md`, ticket `production-context-files`), but `/workspace` is chowned to `flyte`, so driving the terminal here should check which user the pod runs as.

## Driven 2026-10-21

From `main` at `956ea36`, dashboard deployed with `devbox/dashboard.py`:

- **Edit mode works.** A workspace notebook created from the blank seed
  launched in Edit (`/launch` → 200), the pod hydrated it (`[sg] hydrated 1
  file(s)`), its kernel venv installed, and marimo served it.
- **Saving works.** A cell added in the editor was saved by the proxy
  (`[sg] saved devbox-check.py`) and was in the dashboard's download from
  the store seconds later. A line appended in the pod just before Stop was
  in the store afterwards too.
- **The terminal works**, as root: Ctrl+` opens it in `/workspace`,
  `whoami` is `root`, `HOME=/root`, and `claude --version` is `2.1.304
  (Claude Code)`. The pod's process is uid 0, and hydrated files are
  root-owned in the `flyte`-owned `/workspace`; nothing failed because of it.
- **Stop only scales to zero here.** After `/stop` the app reads `App
  scaled to zero` with desired state STOPPED, and its Knative service stays,
  so the notebook's still-open tab (it polls `/__sg__/save-status` every
  10 s) started a new pod within a minute. Deleting the notebook removed the
  service. Union removes the service on Stop.

Nothing needed a code change. Both devbox facts went into `devbox/setup.sh`'s
"What it can't fix", riding on PR #73.

## Outcome

Edit mode, saving and the terminal were driven on the devbox on 2026-10-21 (above) and needed no code change. The two devbox facts (Stop only scales to zero; pods run as root) went into `devbox/setup.sh`'s "What it can't fix", riding on PR #73 (merge `0f43b8b`). Nothing left.
