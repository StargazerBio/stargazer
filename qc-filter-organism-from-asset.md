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

## Decision

The asset's `organism` is the one source of truth (decided 2026-10-20 by the
lead, on the user's delegation). `qc_filter` and `scrna_clustering_pipeline`
lose their `organism` argument. `qc_filter` picks the prefixes from
`adata.organism`, matched case-insensitively against `human` and `mouse`.
An asset whose `organism` is empty or unsupported makes `qc_filter` raise a
`ValueError` naming the field and the supported values, rather than default.
Unlabeled AnnData assets in the repo's own data paths get labeled at the
source instead of a default coming back.

- [ ] Tests: a mouse-labeled asset gets mouse prefixes; an unlabeled or
      unsupported one raises
- [ ] `qc_filter` reads `adata.organism`; the argument is gone
- [ ] `scrna_clustering_pipeline` drops its `organism` argument
- [ ] Every caller, fixture, bundle, notebook and doc checked for
      `organism=` or unlabeled AnnData
