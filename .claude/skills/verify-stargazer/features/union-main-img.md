# Notebook-declared images on Union

A workspace notebook that sets `main_img` in its setup block launches on that image. The first launch after a change waits while Union's remote builder builds it (the tile spins), then the notebook opens with the declared tools on its PATH. A relaunch reuses the built image. This runs on the Union tenant as the test account, because only Union has an image builder.

## Sub-features

- `main-img-build` builds the declared image on the first launch and serves the notebook on it.
- `main-img-kernel` gives the notebook's kernel a `notebook_base` on the deployed notebook image, and `main_img` as a `flyte.Image`.
- `main-img-reuse` serves a stopped notebook again on the same image, with no build.

## How to get to it (user POV)

- Open the dashboard, open a workspace notebook in Edit, add `main_img = notebook_base.with_apt_packages("<package>")` to its setup block (after `from stargazer.notebooks import notebook_base`), stop it and launch it again.

## Driving it

Driven through the test account's dashboard in Chrome (Claude in Chrome), with two helper scripts for setup and checks.

Preconditions:

- `.flyte/union.yaml` is linked into the checkout, and the Flyte CLI is signed in as an org admin.
- Chrome is signed in to GitHub as the test account. Sign in to the console (`https://stargazerbio.us-west-2.unionai.cloud/v2`) with its **Continue with Github (Stargazer Bio)** button, then open app URLs from that page with `location.href`; a direct navigate through the login redirect lands in the wrong tab.
- Export `STARGAZER_TARGET=union` for every `union_dashboard.py` call.

Steps:

- **Deploy.** `STARGAZER_WORKSPACE_ROOT=s3://union-us-west-2-stargazerbio/stargazer STARGAZER_STORE_REGION=us-west-2 uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy` redeploys only the test account's dashboard from the checkout and prints its URL.
- **Seed.** `uv run python .claude/skills/verify-stargazer/scripts/union_seed_notebook.py <package>` writes `main-img-probe.py` (tile "main_img probe") into the test account's workspace, declaring that apt package. Pick one not built on this base before (`tabix` and `jq` have been); any change to the notebook image also forces a build.
- **Launch.** On the dashboard, click **Run** on the "main_img probe" tile by its coordinates. It spins through the build and the deploy (63 s for one apt package), then shows **Open: Run Mode** and **Stop**. Open it: the page reads `PROBE-TOOL: /usr/bin/<package> …`, `PROBE-BASE: <the deployed …:notebook-app-<hash>>` and `PROBE-MAIN: Image`. This covers `main-img-build` and `main-img-kernel`.
- **Check.** `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py check nb-main-img-probe-run`: the served image is `…:notebook-custom-<hash>`, the pod's `STARGAZER_NOTEBOOK_IMAGE` is the deployed `…:notebook-app-<hash>`, and the newest run is a succeeded `build-image`.
- **Reuse.** Click **Stop**, then **Run** again. `check` shows the same served image and no new `build-image` run. This covers `main-img-reuse`.
- **Teardown.** `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py teardown` stops the probe app and the dashboard and prints `live runs: []`.
- **Proof.** Keep the notebook's page text from the launch and the `check` output from the launch and the reuse.

## Gotchas

- `stargazer-users upgrade` redeploys every user's dashboard. Use `union_dashboard.py deploy`, which deploys only the test account's.
- Clicking tile buttons by element reference (`ref_…`) can fail to submit; click by coordinates from a screenshot.
- A failed launch raises a browser alert, which blocks Claude in Chrome. Cover the failure cases with `tests/unit/test_notebook_image.py` and `tests/unit/test_app.py`, or call `/launch` with `fetch` from the dashboard page and read the JSON.
- The seed runs in a task pod because the workspace bucket may not be writable with your own AWS access. Its task module imports only `flyte`, since the pod loads it from a bare Flyte image.
