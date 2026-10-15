---
title: normalize stores normalized counts in the counts layer
status: doing
priority: high
created: 2026-10-09
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
- Side effect: `find_markers` tests on this layer, and scanpy's
  `rank_genes_groups` expects log-normalized data. On raw counts it warns
  ("It seems you use rank_genes_groups on the raw count data"), once per
  sample in the notebook log, and computes fold changes as if the input were
  log1p.
