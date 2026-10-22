# Notebook-declared environments on Union

A workspace notebook that sets `main_env` in its setup block launches in that environment: on its image, with its resources. The basic workspace template declares one (2 CPUs, 4Gi, `bcftools` in the image), so a notebook created from it exercises the whole path. The first launch after an image change waits while Union's remote builder builds the image (the tile spins), then the notebook opens with the declared tools on its PATH. A relaunch reuses the built image. This runs on the Union tenant as the test account, because only Union has an image builder.

## Sub-features

- `main-env-build` builds the declared image on the first launch and serves the notebook on it.
- `main-env-kernel` gives the notebook's kernel a `notebook_base` on the deployed notebook image and a `notebook_env` to clone.
- `main-env-resources` gives the pod the declared CPU and memory, and the default disk.
- `main-env-reuse` serves a stopped notebook again on the same image, with no build.

## How to get to it (user POV)

- On the dashboard, create a notebook from **Basic** and launch it. Its section 0 shows where `bcftools` resolves.
- Or open any workspace notebook's gear and edit `main_env` in its setup block (`notebook_env.clone_with(name=..., image=notebook_base.with_apt_packages("<package>"), resources=flyte.Resources(...))`), then launch it again.

## Driving it

Driven through the test account's dashboard in Chrome (Claude in Chrome), with a helper script for deploying, checking and tearing down.

Preconditions:

- `.flyte/union.yaml` is linked into the checkout, and the Flyte CLI is signed in as an org admin.
- Chrome is signed in to GitHub as the test account. Sign in to the console (`https://stargazerbio.us-west-2.unionai.cloud/v2`) with its **Continue with Github (Stargazer Bio)** button, then open app URLs from that page with `location.href`; a direct navigate through the login redirect lands in the wrong tab.
- Export `STARGAZER_TARGET=union` for every `union_dashboard.py` call.

Steps:

- **Deploy.** With the tenant's `STARGAZER_WORKSPACE_ROOT` and `STARGAZER_DSQL_CLUSTER_ARN` exported (from infra's `tenant.env`), `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy` redeploys only the test account's dashboard from the checkout and prints its URL.
- **Create.** In the dashboard's create tile, type a name not used before (an existing one is refused), choose **Basic**, and click **Create**. A tile for it appears in Workspace.
- **Launch.** Click **Run** on that tile by its coordinates. On the first launch of a template notebook since the last deploy, it spins through the build and the deploy (about a minute for one apt package), then shows **Open: Run Mode** and **Stop**. Open it: section 0 reads `bcftools → /usr/bin/bcftools`. This covers `main-env-build`.
- **Check.** `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py check nb-<slug>-run`: the served image is `…:notebook-custom-<hash>`, the requests are the declared `CPU` and `MEMORY` with the default `EPHEMERAL_STORAGE` (the spec carries no limits; Union applies the requests as limits, which the Resources step shows), the pod's `STARGAZER_NOTEBOOK_IMAGE` is the deployed `…:notebook-app-<hash>`, and the newest run is a succeeded `build-image` (or no new run, when another notebook already built the same declaration on this base). This covers `main-env-kernel` together with section 0 rendering at all, since the setup block imports `notebook_base` and `notebook_env`.
- **Resources.** Launch the same notebook in **Edit**, open the dropdown terminal (Ctrl+`) and run `cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max`: the CPU quota over its period is the declared CPUs, and the memory is the declared limit in bytes. This covers `main-env-resources`.
- **Reuse.** Click **Stop**, then **Run** again. `check` shows the same served image and no new `build-image` run. This covers `main-env-reuse`.
- **Teardown.** `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py teardown` stops the notebook's app and the dashboard and prints `live runs: []`.
- **Proof.** Keep section 0's text from the launch and the `check` output from the launch and the reuse. The created notebook stays in the test account's workspace; delete it from its tile if you want it gone.

## Gotchas

- `stargazer-users upgrade` redeploys every user's dashboard. Use `union_dashboard.py deploy`, which deploys only the test account's.
- Clicking tile buttons by element reference (`ref_…`) can fail to submit; click by coordinates from a screenshot.
- A failed launch raises a browser alert, which blocks Claude in Chrome. Cover the failure cases with `tests/unit/test_notebook_environment.py` and `tests/unit/test_app.py`, or call `/launch` with `fetch` from the dashboard page and read the JSON.
- A workspace notebook is a copy of the template at creation, so a template change needs a newly created notebook to show up.
