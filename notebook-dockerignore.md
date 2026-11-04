---
title: notebook-dockerignore
status: doing
priority: high
created: 2026-11-04
---
Every task image a hosted notebook's kernel builds uploads a 540 MB build context. The MCP server's pixi environment lives in `/stargazer/.pixi/envs/mcp`, inside the source folder `_with_source` copies into each task image (`core_image()` for the tutorials and template, `task_image()` for gatk and scrna). Flyte filters a source folder by a `with_dockerignore` layer's file, else the `.dockerignore` at `flyte.init`'s `root_dir`, which is the cwd, or `/stargazer/src` in a pod (`init_flyte` chdirs there). Neither has one. The fix: `_with_source` adds `with_dockerignore(PROJECT_ROOT / ".dockerignore")`, and the notebook image copies the repo's `.dockerignore` (which excludes `.pixi/`) into `/stargazer`.

A first attempt only copied the file into `/stargazer`; the hosted rerun (image `sha256:cf38025e…`) still printed `Context size is 539.78 MB`, since nothing reads it there. Local check of the real fix, `core_image()` with the cwd at `src/` and `.pixi/` present: 530.1 MB without the layer, 0.9 MB with it.

Measured before the fix (image `ghcr.io/stargazerbio/debug@sha256:3a33f76d…`, main's tree): the hosted Execution tutorial's remote run printed `Context size is 539.78 MB`, the upload took about 3 min before the build was submitted, then the `stargazer-tutorial` image built in 43 s and run `u7m2pqknhvvkjtfhg4p9` succeeded.

## To check later, not in this PR

Running the Execution tutorial's cells made marimo add `flyte==2.12.4` to `execution.py`'s header with `pixi add --script` (pod log: `Adding to sandbox: /usr/local/bin/pixi add --script /stargazer/src/stargazer/notebooks/tutorials/execution.py --pypi flyte==2.12.4`). The file is in `/stargazer`, so nothing is saved, but it rewrites the header of a built-in notebook in the pod and may re-solve its environment. Check whether the uv sandbox did the same, and whether the tutorials' headers should list `flyte` themselves.

## Verification recipe

The pixi-notebook-sandbox ticket's recipe, Hosted: push the branch's image to `ghcr.io/stargazerbio/debug:notebook-dockerignore`, deploy u-pryce's dashboard with `STARGAZER_NOTEBOOK_IMAGE` set to it, `POST /launch` `slug=execution mode=edit section=tutorials`, run all cells. Passes when the remote cell's log shows no `Context size` warning (or one far under 540 MB), the image builds, the run succeeds and `local CIDs == remote CIDs → True`.

Related: [[board]], [[pixi-notebook-sandbox]], [[flyte-images]]
