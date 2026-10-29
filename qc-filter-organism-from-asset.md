---
title: qc-filter-organism-from-asset
status: done
priority: low
created: 2026-10-14
pr: 61
---

`qc_filter` chooses the mitochondrial, ribosomal and hemoglobin prefixes from
its own `organism` argument (default `human`), but stamps its output with the
input asset's `organism`. The two can disagree: an asset labeled `mouse` run
with the default filters on `MT-` and stores the result as `mouse`.
`scrna_clustering_pipeline` passes its own `organism` argument through too.
Reading the asset's `organism` would leave one source of truth, at the cost
of the argument, and an unlabeled asset would need a default.

Found in ticket `scrna-demo-organism`.

## Decision

The asset's `organism` is the one source of truth (decided 2026-10-20 by the
lead, on the user's delegation). `qc_filter` and `scrna_clustering_pipeline`
lose their `organism` argument. `qc_filter` picks the prefixes from
`adata.organism`, matched case-insensitively against `human` and `mouse`.
An asset whose `organism` is empty or unsupported makes `qc_filter` raise a
`ValueError` naming the field and the supported values, rather than default.
Unlabeled AnnData assets in the repo's own data paths get labeled at the
source instead of a default coming back.

- [x] Tests: a mouse-labeled asset gets mouse prefixes; an unlabeled or
      unsupported one raises
- [x] `qc_filter` reads `adata.organism`; the argument is gone
- [x] `scrna_clustering_pipeline` drops its `organism` argument
- [x] Every caller, fixture, bundle, notebook and doc checked for
      `organism=` or unlabeled AnnData

## Verification

Branch `fix/qc-filter-organism-from-asset`, PR #61. Measured 2026-10-20.

- New tests fail on `main`'s code for the expected reason (mouse asset flags
  0 genes where 10 MT, 20 ribo, 5 hb are expected; unlabeled and `zebrafish`
  do not raise), and pass after: scrna tasks tier 19 passed, unit tier 502.
- The scRNA notebook exports with exit 0 and 14/14 `ok` checks; `s1d1` is
  stored as `human` with 13 MT genes flagged and 6,307 cells kept, as in
  ticket `scrna-demo-organism`.
- `scrna_clustering_pipeline` run locally through Flyte: labeled `s1d1`
  reaches `annotated` (6,307 cells); an unlabeled copy fails with
  `AnnData 'unlabeled' has organism ''; set its organism field to one of:
  human, mouse`.
- The only caller passing `organism=` was the pipeline itself. Every AnnData
  the repo produces (bundle, test fixtures, verify seed) is already labeled.

Found along the way: ticket `registry-type-names-py314`.

## Outcome

PR #61 (`36ea20f`, merged 2026-10-21). `qc_filter` takes the organism from
its input `AnnData` and raises on an unlabeled or unsupported one; the
pipeline no longer passes `organism=`. Verified as above. Its PR also
carried the AGENTS.md rule to answer a merged PR's comments (`1140e8e`).
No comments were left on it. Left: ticket `registry-type-names-py314`.
