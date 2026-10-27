---
title: The scRNA notebook runs on its own pod's machine
status: done
priority: normal
created: 2026-10-26
pr: 86
---

In a hosted notebook, the scRNA notebook's **On this machine** fails at `preprocess`: `qc_filter`'s scrublet step raises `` `threshold` is None and thus scrublet requires `scikit-image` `` (measured 2026-10-26, test account, Edit mode). The notebook's PEP 723 header lists `scanpy`, `anndata`, `matplotlib`, `numpy` and `stargazer`, but not what the `bio` extra adds for scanpy's lazy imports (`scikit-image`, `igraph` for Leiden), so the sandbox venv `marimo --sandbox` builds lacks them. Locally it passes because the checkout's venv has every extra. **On the cluster** is unaffected: the tasks run on `scrna_env`'s image. Likely fix: depend on `stargazer[bio]` in the header instead of listing scanpy's packages; verify with a hosted Run-mode drive on the default setting.

## Verification

Measured 2026-10-26 on branch `fix/scrna-notebook-hosted-deps` (`90ea16b`).

- **Before, sandbox export** (header as on `main`): exit `1`, `` `threshold` is None and thus scrublet requires `scikit-image` `` in `qc_filter`, the error the hosted pod gave.
- **After, sandbox export:** exit `0`; the sandbox installed `scikit-image==0.26.0`; `check_anndata.py` reads `ok` for both samples at every stage, `raw` through `annotated` (s1d1 6,307 cells, s1d3 7,157 after QC).
- **After, hosted Run mode** (test account, built-in browser): the deploy rebuilt the notebook image (build run `ub8fk7tcrk9bxdkbqbs6`) and served `notebook-app-2c4ddebb6479a76b584174bd8e5ab750`. With **Run** on **On this machine**, every section rendered with no error: s1d1 6,307 cells, 16 clusters; s1d3 7,157 cells, 17 clusters. No new runs in `u-pryce` during the drive, so the tasks ran in the notebook's process. Teardown: `live runs: []`.
- Unit tier: 492 passed.

## Verification recipe: scRNA notebook on its own machine

With **Run** on its default, **On this machine**, the scRNA notebook runs `preprocess` and `cluster_and_annotate` inside the notebook's own process, so every package those tasks import has to be in the sandbox environment `marimo --sandbox` builds from the notebook's PEP 723 header. A user who opens the notebook sees the pipeline run through to the side-by-side UMAPs and the summary table.

### Sub-features

- `sandbox-deps`: the header's environment imports everything the scRNA tasks import, scanpy's lazy imports included (`scikit-image` for scrublet, `igraph` for Leiden).
- `hosted-local-run`: on a hosted pod, the notebook in Run mode finishes every section on its own machine.

### How to get to it (user POV)

- On the dashboard, the Workflows section's scRNA tile → **Run** → **Open: Run Mode**. The **Run** control above section 4 starts on **On this machine**.

### Driving it

Preconditions: the `verify-stargazer` local-notebook block has run and the scRNA samples are seeded (recipe `normalize-counts-layer`'s seed script); uv is 0.7.21 or newer, which `marimo --sandbox` needs.

- **Sandbox export (`sandbox-deps`).** The header's source path points at `/stargazer`, so copy the notebook with it pointed at the checkout, then export in sandbox mode:

```bash
sed "s#path = \"/stargazer\"#path = \"$PWD\"#" src/stargazer/notebooks/workflows/scrna_pipeline.py > "$RUN_DIR/scrna_sandbox.py"
uv run --all-extras marimo export html --sandbox "$RUN_DIR/scrna_sandbox.py" -o "$RUN_DIR/evidence/sandbox.html" > "$RUN_DIR/evidence/sandbox.log" 2>&1; echo $?
uv run python "$RUN_DIR/check_anndata.py"
```

  Exit `0`, no `scikit-image` in the log, and every check line `ok`. Before the fix, exit `1` with `` `threshold` is None and thus scrublet requires `scikit-image` ``.
- **Hosted Run mode (`hosted-local-run`).** Deploy the test account's dashboard from the checkout (`union_dashboard.py deploy`; the notebook image carries the notebook), open the scRNA tile in Run mode as the test account, leave **Run** on **On this machine**, and wait for the page to finish. Sections 4 to 6 render the UMAPs and the summary table, with no error. Then `union_dashboard.py teardown`: `live runs: []`.

### Gotchas

- A plain `marimo export` without `--sandbox` runs in the checkout's venv, which has every extra, so it passes even with the bug.
- `marimo --sandbox` refuses uv older than 0.7.21.

## Outcome

Shipped in PR #86 (merge `72dd7db`). The scRNA notebook's PEP 723 header depends on `stargazer[bio]`, so its sandbox environment has `scikit-image` and `igraph`; `docs/architecture/notebook.md` and the notebook agent's context say a notebook running the scRNA tasks in its own process needs that extra. Verified by a local `marimo export html --sandbox` before (the scikit-image error) and after (every stage `ok`), and by a hosted Run-mode drive on the test account that finished on the notebook's own machine (Verification above). Nothing left. No review comments.
