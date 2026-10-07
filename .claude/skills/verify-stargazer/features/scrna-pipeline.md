# scRNA-seq pipeline notebook

A user picks samples from the `scrna_demo` bundle, sees raw QC histograms, and runs two workflows across every picked sample in parallel: `preprocess` (QC filter, normalize, select features, reduce dimensions) and `cluster_and_annotate` (Leiden clustering, marker genes). The notebook ends with side-by-side UMAPs and a per-sample summary table of cells, genes, clusters, and CID.

## Sub-features

- `scrna-load` loads the raw AnnData for each picked sample from the asset store.
- `scrna-fetch` fetches the `scrna_demo` bundle when the store has no raw samples.
- `scrna-preprocess` runs `preprocess` once per sample, fanned out with `asyncio.gather`.
- `scrna-cluster` runs `cluster_and_annotate` once per sample on the preprocessed outputs.
- `scrna-summary` renders one UMAP and one summary row per sample.

## How to get to it (user POV)

- Open `src/stargazer/notebooks/workflows/scrna_pipeline.py` in `marimo edit` or `marimo run`. Both samples (`s1d1`, `s1d3`) are picked by default.

## Driving it with marimo export

Preconditions:

- Seeded with `scripts/seed_scrna.py`. That covers `scrna-load` and skips `scrna-fetch`.
- `scripts/doctor.sh` exits `0`.

Steps:

- **Run every cell with the default picks.** Run `uv run marimo export html src/stargazer/notebooks/workflows/scrna_pipeline.py -o "$RUN_DIR/evidence/scrna-pipeline.html" > "$RUN_DIR/evidence/scrna-pipeline.log" 2>&1`. This takes about 2 minutes locally. Exit code `0`.
- **Check every stage's outputs.** Run `uv run python .claude/skills/verify-stargazer/scripts/check_anndata.py | tee "$RUN_DIR/evidence/scrna-pipeline.check.txt"`. Every line reads `ok`, and both samples appear at every stage from `raw` through `annotated`.
- **Proof.** Keep the HTML, the log, and the check output. The check output is the load-bearing artifact.

## Gotchas

- An export exit of `0` with check lines reading `MISMATCH` means the notebook rendered another sample's data. Parallel samples share one cache directory, so each scRNA task must write a per-sample filename (`<sample_id>_qc_filtered.h5ad`, and so on).
- A `MISSING` line means two samples produced byte-identical files at that stage. The index keeps one row per CID, so the second sample's metadata replaced the first's, and the log shows a WARNING naming the CID.
- `scrna-fetch` hits public IPFS gateways, which rate-limit with HTTP `429` after a few full downloads. Drive it at most once per run, and only when the change touches fetching.
- With a real `PINATA_JWT` in the environment, `assemble()` also searches Pinata's public index, so a drive can pick up public records that aren't part of the run.
- `flyte.init_from_config()` in the first cell reads `.flyte/config.yaml` but does not need the devbox. Tasks called directly from cells run in-process.
