---
title: normalize-counts-layer
status: done
priority: high
created: 2026-10-09
pr: 32
---

`normalize` copies `X` into `layers["counts"]` after `normalize_total`,
so the layer holds normalized counts (every row sums to ~498 on the
fixture), while its docstring, and `find_markers`, which tests on that
layer, say raw counts (measured).

Found in the docs correctness sweep (2026-10-09, #18).

## Verification

Branch `fix/normalize-counts-layer`. Measured 2026-10-14:

- `test_normalize_layers` now requires the `counts` layer to equal the input
  exactly. It failed before the fix (1.018 where the raw count is 1) and
  passes after; all 15 scRNA task tests pass in the scrna image.
- The scRNA pipeline notebook (verify-stargazer `scrna-pipeline`) exports
  with exit 0 and every `check_anndata.py` line `ok`. In both samples' stored
  `normalized` file, `counts` equals the `qc_filtered` matrix and is integral;
  row sums run 503-150722 instead of all sitting at the median.
- `find_markers` tested on this layer, and scanpy's `rank_genes_groups`
  expects log-normalized data. On raw counts it warns ("It seems you use
  rank_genes_groups on the raw count data"), which fired once per sample in
  the notebook log, and computes fold changes as if the input were log1p. The
  same branch now tests on `X`, which is still log-normalized there.
  `test_find_markers_tests_log_normalized_data` failed before (1.948 vs 1.376)
  and passes after. A second notebook drive: export exit 0, all 14 checks
  `ok`, no raw-count warnings, and each sample's markers record `layer=None`.

## Outcome

Shipped in PR #32 (merged 2026-10-15). `normalize` keeps the raw counts in
`layers["counts"]`, and `find_markers` tests on the log-normalized `X`, which
is what scanpy's `rank_genes_groups` expects.

Verified with two tests that failed before and pass after, the scrna image's
task tests, and two drives of the scRNA pipeline notebook: every
`check_anndata.py` check `ok`, the stored `counts` layer equal to the
`qc_filtered` matrix, and no raw-count warnings.

Left: nothing.

## Verification recipe: scRNA-seq pipeline notebook

A user picks samples from the `scrna_demo` bundle, sees raw QC histograms, and runs two workflows across every picked sample in parallel: `preprocess` (QC filter, normalize, select features, reduce dimensions) and `cluster_and_annotate` (Leiden clustering, marker genes). The notebook ends with side-by-side UMAPs and a per-sample summary table of cells, genes, clusters, and CID.

### Sub-features

- `scrna-load` loads the raw AnnData for each picked sample from the asset store.
- `scrna-fetch` fetches the `scrna_demo` bundle when the store has no raw samples.
- `scrna-preprocess` runs `preprocess` once per sample, fanned out with `asyncio.gather`.
- `scrna-cluster` runs `cluster_and_annotate` once per sample on the preprocessed outputs.
- `scrna-summary` renders one UMAP and one summary row per sample.

### How to get to it (user POV)

- Open `src/stargazer/notebooks/workflows/scrna_pipeline.py` in `marimo edit` or `marimo run`. Both samples (`s1d1`, `s1d3`) are picked by default.

### Driving it with marimo export

Preconditions:

- The `verify-stargazer` skill's local-notebook launch block has run, and its `doctor.sh` exits `0`.
- The seed and check scripts are pulled from history into the run directory, from the repo root:

```bash
git show 80dfd7e:.claude/skills/verify-stargazer/scripts/seed_scrna.py | sed 's/Path(__file__).resolve().parents\[4\]/Path.cwd()/' > "$RUN_DIR/seed_scrna.py"
git show 80dfd7e:.claude/skills/verify-stargazer/scripts/check_anndata.py > "$RUN_DIR/check_anndata.py"
uv run python "$RUN_DIR/seed_scrna.py"
```

  Seeding copies the `scrna_demo` raw samples from `~/.stargazer/verify-cache/` (downloading once on a miss). That covers `scrna-load` and skips `scrna-fetch`.

Steps:

- **Run every cell with the default picks.** Run `uv run marimo export html src/stargazer/notebooks/workflows/scrna_pipeline.py -o "$RUN_DIR/evidence/scrna-pipeline.html" > "$RUN_DIR/evidence/scrna-pipeline.log" 2>&1`. This takes about 2 minutes locally. Exit code `0`.
- **Check every stage's outputs.** Run `uv run python "$RUN_DIR/check_anndata.py" | tee "$RUN_DIR/evidence/scrna-pipeline.check.txt"`. Every line reads `ok`, and both samples appear at every stage from `raw` through `annotated`.
- **Proof.** Keep the HTML, the log, and the check output. The check output is the load-bearing artifact.

### Gotchas

- An export exit of `0` with check lines reading `MISMATCH` means the notebook rendered another sample's data. Parallel samples share one cache directory, so each scRNA task must write a per-sample filename (`<sample_id>_qc_filtered.h5ad`, and so on).
- A `MISSING` line means two samples produced byte-identical files at that stage. The index keeps one row per CID, so the second sample's metadata replaced the first's, and the log shows a WARNING naming the CID.
- `scrna-fetch` hits public IPFS gateways, which rate-limit with HTTP `429` after a few full downloads. Drive it at most once per run, and only when the change touches fetching.
- With a real `PINATA_JWT` in the environment, `assemble()` also searches Pinata's public index, so a drive can pick up public records that aren't part of the run.
- `init_flyte()` in the first cell reads `.flyte/config.yaml` but does not need the devbox. Tasks called directly from cells run in-process.

Related: [[scrna-demo-organism]], [[board]].
