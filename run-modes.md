---
title: run-modes
status: doing
priority: normal
created: 2026-11-09
---

Stargazer code runs from a script, a notebook (locally, in the stargazer image under docker, or hosted), the MCP agent, or a workflow's pod, and a task's body runs in-process, in its image under docker, or in a cluster pod (Union or the devbox). Which packages each of those needs is hard to explain today: a notebook's header lists a domain's tools only so "On this machine" can run SDK tasks in the kernel, and a notebook's own tasks get their packages from image layers the author adds by hand, beside the header. This ticket settles one happy path that fits in four sentences, conventions for the SDK, and a "your own risk" zone for everything else.

## The happy path

1. **Every SDK task runs in its domain's environment, wherever it runs.** It's declared once, in the PEP 723 header of `tasks/<domain>/env.py`. The cluster runs it as the task image, docker runs that image, and "Here" installs the same header and lock with pixi.
2. **A notebook's kernel is its header.** marimo writes it as you import. List what your cells use, nothing else.
3. **Calling an SDK task from a notebook needs nothing in your header.** "Here" runs it in its own environment on your machine, not in your kernel; "Cluster" in its task image.
4. **Your notebook's own tasks run in your notebook's environment.** "Here" in your kernel; on the cluster the template builds the image from your notebook's header, so what you installed while experimenting is what the cluster gets.

So the SDK's tasks bring their own environment, and a notebook's tasks use the notebook's. In both cases one header is both the place a task's packages are listed and the source of its image, so the two can't drift: `task_image(__file__)` already builds an SDK task image with `flyte.Image.from_pixi_script` on its `env.py`.

## Conventions

- **SDK:** every `TaskEnvironment` under `stargazer.tasks` builds with `task_image(__file__)` from its own `env.py` (AGENTS.md already says so). A domain's packages are listed only in its header and imported inside task bodies. This stays a written convention, reviewed in PRs: no test or lint enforces it, since the shape may still change.
- **Notebook authors:** anything goes. The template shows the happy path.

## Your own risk

Supported, not the happy path:
- Any other `flyte.Image` on a notebook's own `TaskEnvironment` (`core_image(...)` plus layers, `from_base`, anything).
- Listing a domain's packages in your header and calling SDK tasks in-process in your kernel.
- An unlocked notebook header, whose cluster image can resolve differently between builds. The run records the image's digest (ticket `notebook-image-digest`), but the header alone doesn't reproduce it.
- gatk joint calling on Apple silicon (GenomicsDB has no arm64 build).

## Plan

Built on `feat/run-modes`, cut from `main` after PR 134 (the docker path) merged, which it reworks, piece by piece in this order.


- [ ] **"Here" for SDK tasks:** install the task's `env.py` header and lock with pixi and run the task in it as a subprocess, in a hosted pod too (it has pixi, not docker). Docker runs the same lock containerized, as the task image, for a host the header can't solve on. Reworks PR 134, which runs every package task under docker. Covers ticket `hosted-local-runs`.
      The environment's SDK must be the kernel's, the way `task_image()` picks it: the header pins the released `stargazer-bio`, so from a checkout the checkout goes on top of the env (editable install or `PYTHONPATH`, as `_with_source` does for the image), or a task edited in a checkout would run as released. From an installed package, the env's `stargazer-bio` is the kernel's version. Either way, inputs and outputs cross between the kernel and the env pickled, so both sides need the same asset classes.
- [ ] **Platforms:** each `env.py` header lists `osx-arm64` beside `linux-64`, locked by `cli/lock_envs.py`. Apple silicon isn't optimized for: whatever doesn't solve or run natively runs in the task image under docker. That's documented, with no platform-specific code around it.
- [ ] **SDK workflows "Here":** the workflow body runs in the caller and each task in its own environment, so a workflow spanning gatk and scRNA works. Flyte 2.12.4's local controller runs children in the caller's process (`direct_dispatch`), so this hooks or wraps it.
- [ ] **Template:** `my_env`, the environment the notebook's own tasks run on, builds from `flyte.Image.from_pixi_script(__file__)`. `main_env`, the pod's `AppEnvironment` on `notebook_base`, is unchanged. The header's `stargazer-bio` comes from `/stargazer`, which resolves only in a pod, so the build reads the header without that line and puts the SDK on top the way `task_image()` does: from a checkout (development), the checkout's source; from an installed package (production, a hosted pod included), the release of the kernel's version from PyPI. marimo's sandbox writes no lock, so the template's image is unlocked (the "your own risk" entry applies to it too).
- [ ] **Headers:** once "Here" lands, the built-in and community notebooks drop domain packages their cells don't import (germline's gatk4, samtools, bwa-mem2).
- [ ] **Docs:** a user guide, "Where your code runs", leading with the four sentences; `docs/architecture/notebook.md` and `configuration.md` for the mechanics.

## Run modes today

For reference while planning. Callers:

| Caller | Kernel environment | Where tasks run |
|---|---|---|
| Script or IDE from a checkout (`pixi run`) | dev env, editable SDK | in-process, or cluster on images built from source |
| Script with `stargazer-bio` installed in your own env | your env | in-process, or cluster on the release's images |
| Notebook locally, `pixi run marimo edit` | dev env | in-process, docker (PR 134), or cluster |
| Notebook locally, sandboxed | its header | in-process, docker (PR 134), or cluster |
| Notebook in the stargazer image, `docker run` | its header | in-process only |
| Notebook hosted | its header | in-process, or cluster |
| MCP agent (local, or the pod's terminal) | the `mcp` env, editable | cluster, images built from source |
| A workflow's pod | its task image | children in their own pods |

Executors: in-process (Flyte local mode), the task image under local docker, a Union pod, a devbox pod.

Related: [[board]], [[local-runs-in-task-image]], [[hosted-local-runs]], [[released-sdk-in-notebooks]], [[notebook-image-digest]], [[marimo-autoadd-headers]], [[pixi-notebook-sandbox]], [[flyte-images]], [[marimo-sandbox]].
