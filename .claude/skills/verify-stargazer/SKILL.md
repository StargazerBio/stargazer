---
name: verify-stargazer
description: "Drive Stargazer the way a user does and capture evidence that a change works, on whichever surface it reaches: a marimo notebook run headless against an isolated asset store, the local devbox, or the Union tenant as the test account. Use before declaring a task, workflow, notebook or app change done, or when asked to verify, prove, or reproduce Stargazer behavior."
---

# Verify Stargazer

Proves user-visible behavior on the real surface: the notebook a user opens, the pods a workflow runs in, the notebook pod a user opens. A passing pytest run is not this proof. Adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack)'s verification skills (MIT).

Pick the surface the change reaches, write or reuse its recipe, drive it, check what it stored, and record the evidence in the PR.

## Keep it general

This skill says how to verify any change on each surface. It holds no recipes, feature maps or scripts for one notebook, workflow or task: those live in the change's ticket, below. A check worth repeating on every change becomes a test in its tier, not a file here.

## Recipes

A change's own verification is a recipe in its ticket, under `## Verification recipe: <feature>`, so it stays runnable without living on `main`. Before driving a change, look for earlier recipes on the same surface or feature and reuse what still holds; each sits beside its ticket's PR and outcome, which date it:

```bash
MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
grep -n '^## Verification recipe' "$MAIN"/planning/*.md
```

Write the change's recipe into its ticket before driving it, in this shape (pstack's feature entry):

- `## Verification recipe: <feature>`, then one paragraph on the user-visible behavior.
- `### Sub-features`: one bullet per behavior, each with a short ID that evidence names.
- `### How to get to it (user POV)`: where a user finds it.
- `### Driving it`: preconditions, then steps whose commands run as written, each with the result that passes.
- `### Gotchas`: what broke or misled along the way.

A script a recipe needs goes in the ticket as a code block, or is pulled from history with `git show <sha>:<path>` into the run directory, never committed to this skill. Run the recipe, and record its evidence in the PR.

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

For anything that runs across pods: workflows, task images, the devbox's object store and Postgres index. The devbox test tier is the driver: `uv run --all-extras pytest -m devbox -rP <tests>` passes the devbox storage settings to every run and reads the index through a port-forward. `-rP` prints each run's URL; keep the output as evidence. When no test covers the change, write one in `tests/devbox/` (the `write-tests` skill).

Preconditions: the devbox is up, infra's `devbox/setup.sh` has run since it was last created (its verify step ends with `✓ Postgres ready`), `FLYTE_IMAGE_REGISTRY=localhost:30000` is exported, and `kubectl config current-context` is `flyte-devbox`.

- The setup clears Flyte's local cache, so run it after a recreate and before the first run, or the run skips images and bundles the wipe deleted.
- A source change rebuilds the images that carry the project before the first run. Pods run emulated on Apple silicon, slower than on Union.
- Submitting from your own shell (not the tests) needs the three devbox storage settings exported and `kubectl port-forward -n flyte svc/rustfs-svc 9000:9000` open (`docs/guides/contributing.md` → Running on the Devbox). Without the port-forward, uploads fail with `All connection attempts failed`.
- Right after a redeploy, Knative can route a request to the previous revision for a few seconds. A test that depends on the new revision can fail on that one request; the pod's log names its revision.

## Union tenant

For what only Union has: its login and RBAC, the remote image builder, notebook launch. Tasks and workflows run there from a checkout with `.flyte/union.yaml` and `STARGAZER_API_KEY_SECRET=UNION_API_KEY` exported.

A notebook or runtime change reaches Union in the image a dashboard launches, which is a release's. To drive it before a release:

1. Build the image from the checkout for amd64 and push it to GHCR under a test tag, never a release tag or `latest`: `docker buildx build --platform linux/amd64 -f runtime/Dockerfile -t ghcr.io/stargazerbio/stargazer:test-<slug> --push .` (`docker login ghcr.io` with `gh auth token` first).
2. Deploy the test account's dashboard from an infra checkout with `STARGAZER_NOTEBOOK_IMAGE` set to that tag, and drive it there: infra's `verify-dashboard` skill.
3. Tear down what you started, and delete the test tag's package version afterwards.

## Helpers

| Script | Does |
|---|---|
| `scripts/doctor.sh` | Read-only check of a local run's environment. Exit 1 on a blocking failure |
