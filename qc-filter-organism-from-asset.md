---
title: qc_filter takes organism separately from its input asset
status: doing
priority: low
created: 2026-10-14
---

`qc_filter` chooses the mitochondrial, ribosomal and hemoglobin prefixes from
its own `organism` argument (default `human`), but stamps its output with the
input asset's `organism`. The two can disagree: an asset labeled `mouse` run
with the default filters on `MT-` and stores the result as `mouse`.
`scrna_clustering_pipeline` passes its own `organism` argument through too.
Reading the asset's `organism` would leave one source of truth, at the cost
of the argument, and an unlabeled asset would need a default.

Found in ticket `scrna-demo-organism`.
