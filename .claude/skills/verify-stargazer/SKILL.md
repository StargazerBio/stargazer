---
name: verify-stargazer
description: "Drive Stargazer the way a user does and capture evidence that a change works, on whichever surface it reaches: a marimo notebook run headless against an isolated asset store, the local devbox, or the Union tenant as the test account. Use before declaring a task, workflow, notebook or app change done, or when asked to verify, prove, or reproduce Stargazer behavior."
---

# Verify Stargazer

Proves user-visible behavior on the real surface: the notebook a user opens, the pods a workflow runs in, the dashboard a user clicks. A passing pytest run is not this proof. Adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack)'s verification skills (MIT).

Pick the surface the change reaches, drive it, check what it stored, and record the evidence in the PR.

## Keep it general

This skill says how to verify any change on each surface. It holds no recipes, feature maps or scripts for one notebook, workflow or task. The drive and the check for a particular change are written for that change, run, and recorded as evidence in its PR. A check worth repeating becomes a test in its tier, not a file here.

## Evidence

- Drive what the user drives, not a script that calls the same tasks.
- Check the stored outputs, not only the rendered page or the exit code. `assemble()` the run's outputs from its index, `fetch()` each, and compare what its keyvalues claim (sample, counts, links to its inputs) with what the file holds. Write that check for the change, inline.
- Record the commands, their exit codes, the check's output, and the run URLs.
- Report a surface that couldn't be reached with what blocked it. Never report it as verified through another path.

## Local notebook

Every run gets its own asset store and evidence directory. All commands run from the repo root.

```bash
export RUN_ID=$(date +%Y%m%d-%H%M%S)
export RUN_DIR=$HOME/.stargazer/verify-runs/$RUN_ID
export STARGAZER_LOCAL=$RUN_DIR/local
export STARGAZER_STORE_ROOT=$RUN_DIR/store
export STARGAZER_INDEX_URL=$RUN_DIR/index.db
export PINATA_JWT=
mkdir -p "$RUN_DIR/evidence"
.claude/skills/verify-stargazer/scripts/doctor.sh
```

The three `STARGAZER_*` paths are the run's whole asset store: the local cache, the stored files, and the index. Without all three, a run shares the user's defaults under `~/.stargazer/`. `PINATA_JWT=` must be explicitly empty, not unset: marimo loads `.env`, which holds a real JWT, and an empty value already in the environment wins over it. With it empty, nothing reaches Pinata, and `assemble()` can't pick up public records that aren't part of the run. `doctor.sh` is read-only; its `FAIL` lines block the drive.

**Seed** the inputs the notebook looks up. A bundle (`src/stargazer/bundles/`) fetches into the run's store with `uv run python -c "import asyncio; from stargazer.bundles import fetch_bundle; asyncio.run(fetch_bundle('<bundle>'))"`. Public IPFS gateways rate-limit with HTTP `429` after a few full downloads, so fetch once per run.

**Drive** with one headless export, which runs every cell and exits:

```bash
uv run marimo export html <notebook.py> -o "$RUN_DIR/evidence/<name>.html" > "$RUN_DIR/evidence/<name>.log" 2>&1
```

Exit `0` means every cell ran. Exit `1` with `Export was successful, but some cells failed to execute` means a cell raised; the log names the exception and the HTML holds the traceback. Exit `0` is not proof: a notebook can run every cell and show the wrong data. Tasks called from cells run in-process, so their tools must be on this machine's PATH; a notebook that needs gatk, bwa or samtools is verified on the devbox instead.

**Clean up** the run's store, which can hold hundreds of MB, and confirm the evidence survived:

```bash
rm -rf "$RUN_DIR/local" "$RUN_DIR/store" "$RUN_DIR"/index.db*
```

## Devbox

For anything that runs across pods: workflows, task images, the devbox's object store and Postgres index, the dashboard. The devbox test tier is the driver: `uv run --all-extras pytest -m devbox -rP <tests>` deploys the dashboard when its tests need it, passes the devbox storage settings to every run, and reads the index through a port-forward. `-rP` prints each run's URL; keep the output as evidence. When no test covers the change, write one in `tests/devbox/` (the `write-tests` skill).

Preconditions: the devbox is up, `devbox/setup.sh` has run since it was last created (its verify step ends with `✓ Postgres ready`), the hosts it prints resolve on this machine, and `kubectl config current-context` is `flyte-devbox`.

- `devbox/setup.sh` clears Flyte's local cache, so run it after a recreate and before the first deploy, or the deploy skips images and bundles the wipe deleted.
- A source change rebuilds the images that carry the project before the first run. Pods run emulated on Apple silicon, slower than on Union.
- Submitting from your own shell (not the tests) needs the three devbox storage settings exported and `kubectl port-forward -n flyte svc/rustfs-svc 9000:9000` open (`docs/guides/contributing.md` → Running on the Devbox). Without the port-forward, uploads fail with `All connection attempts failed`.
- Right after a redeploy, Knative can route a request to the previous revision for a few seconds. A test that depends on the new revision can fail on that one request; the pod's log names its revision.

## Union tenant

For what only Union has: its login and RBAC, the remote image builder, notebook launch. Driven through the test account's dashboard in Chrome (Claude in Chrome), with `scripts/union_dashboard.py` for the rest.

Preconditions: `.flyte/union.yaml` is linked into the checkout and the Flyte CLI is signed in as an org admin; `STARGAZER_TARGET=union` is exported, with infra's `tenant.env` for a deploy; Chrome is signed in to GitHub as the test account.

- `union_dashboard.py deploy` redeploys only the test account's dashboard from the checkout and prints its URL. Never `stargazer-users upgrade`, which redeploys every user's.
- Sign in to the console (`https://stargazerbio.us-west-2.unionai.cloud/v2`) with its **Continue with Github (Stargazer Bio)** button, then open app URLs from that page with `location.href`; a direct navigate through the login redirect lands in the wrong tab.
- Click tile buttons by coordinates from a screenshot; clicking by element reference can fail to submit. A failed launch raises a browser alert, which blocks Claude in Chrome: call the endpoint with `fetch` from the dashboard page and read the JSON instead.
- `union_dashboard.py check <app>` prints an app's served image, its resources, its pod's notebook base and the newest runs.
- A workspace notebook is a copy of its template at creation, so a template change needs a newly created notebook.
- **Teardown** is part of the drive: `union_dashboard.py teardown` stops every app in the test account's project and prints the live runs, which must be `[]`.

## Helpers

| Script | Does |
|---|---|
| `scripts/doctor.sh` | Read-only check of a local run's environment. Exit 1 on a blocking failure |
| `scripts/union_dashboard.py deploy\|check <app>\|teardown` | Redeploys, inspects or stops the Union test account's dashboard and its apps |
