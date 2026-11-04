---
title: notebook-dockerignore
status: done
priority: high
created: 2026-11-04
pr: 133
---
Every task image a hosted notebook's kernel builds uploads a 540 MB build context. The MCP server's pixi environment lives in `/stargazer/.pixi/envs/mcp`, inside the source folder `_with_source` copies into each task image (`core_image()` for the tutorials and template, `task_image()` for gatk and scrna). Flyte filters a source folder by a `with_dockerignore` layer's file, else the `.dockerignore` at `flyte.init`'s `root_dir`, which is the cwd, or `/stargazer/src` in a pod (`init_flyte` chdirs there). Neither has one. The fix: `_with_source` adds `with_dockerignore(PROJECT_ROOT / ".dockerignore")`, and the notebook image copies the repo's `.dockerignore` (which excludes `.pixi/`) into `/stargazer`.

A first attempt only copied the file into `/stargazer`; the hosted rerun (image `sha256:cf38025e…`) still printed `Context size is 539.78 MB`, since nothing reads it there. Local check of the real fix, `core_image()` with the cwd at `src/` and `.pixi/` present: 530.1 MB without the layer, 0.9 MB with it.

Measured before the fix (image `ghcr.io/stargazerbio/debug@sha256:3a33f76d…`, main's tree): the hosted Execution tutorial's remote run printed `Context size is 539.78 MB`, the upload took about 3 min before the build was submitted, then the `stargazer-tutorial` image built in 43 s and run `u7m2pqknhvvkjtfhg4p9` succeeded.

Verified on this branch's image (`debug:notebook-dockerignore@sha256:33c99d20…`): the hosted Execution tutorial's remote cell printed no context warning, the tutorial image built in 17 s, and run `uk4f4pz98h5d8wd49g62` succeeded with the same CIDs as the local run.

## To check later, not in this PR

Running the Execution tutorial's cells made marimo add `flyte==2.12.4` to `execution.py`'s header with `pixi add --script` (pod log: `Adding to sandbox: /usr/local/bin/pixi add --script /stargazer/src/stargazer/notebooks/tutorials/execution.py --pypi flyte==2.12.4`). The file is in `/stargazer`, so nothing is saved, but it rewrites the header of a built-in notebook in the pod and may re-solve its environment. Check whether the uv sandbox did the same, and whether the tutorials' headers should list `flyte` themselves.

## Verification recipe

The pixi-notebook-sandbox ticket's recipe, Hosted: push the branch's image to `ghcr.io/stargazerbio/debug:notebook-dockerignore`, deploy u-pryce's dashboard with `STARGAZER_NOTEBOOK_IMAGE` set to it, `POST /launch` `slug=execution mode=edit section=tutorials`, run all cells. Passes when the remote cell's log shows no `Context size` warning (or one far under 540 MB), the image builds, the run succeeds and `local CIDs == remote CIDs → True`.

## Outcome

Shipped in PR 133 (merged 2026-11-04). `_with_source` passes the checkout's `.dockerignore` to every task image with `with_dockerignore`, and the notebook image copies it into `/stargazer`. Without it, a hosted kernel's task images uploaded the MCP environment in `.pixi/`.

Verified on Union: the hosted Execution tutorial's build context went from 539.78 MB to under 5 MB, the image built in 17 s, and the run succeeded. The unit tier passed (266). There were no review comments.

Left: the header rewrite by marimo moves to [[marimo-autoadd-headers]].

Related: [[board]], [[marimo-autoadd-headers]], [[pixi-notebook-sandbox]], [[flyte-images]]
