---
title: scrna-demo-organism
status: done
priority: normal
created: 2026-10-14
pr: 33
---

`src/stargazer/bundles/scrna_demo.yaml` describes the files as "mouse brain
data (10x Genomics)" and gives both `organism: mouse`. The files are human:
36,601 human gene symbols (Cell Ranger's GRCh38 feature set, starting
`MIR1302-2HG`, `FAM138A`, `OR4F5`), 13 `MT-` genes and no `mt-` genes, and the
pipeline's top markers are immune-cell genes (`LYZ`, `LST1`, `IRF8`, `IL32`).
Measured 2026-10-14 on both files.

`qc_filter` picks the mitochondrial prefix from its `organism` argument. The
notebook calls it with the default, `human`, so its filter works by accident.
`scrna_clustering_pipeline(organism="mouse")`, the label a user would copy
from the bundle, would flag no mitochondrial genes and filter nothing on
`max_pct_mt` (inferred from the code). Every stored asset also carries
`organism: mouse` from the raw file.

Fix the bundle's description and keyvalues, and find out what the data
actually is (likely a PBMC sample; the tutorials' text may describe it as
brain).

Found while verifying ticket `normalize-counts-layer`.

## Verification

Branch `fix/scrna-demo-organism`. The data is human bone marrow mononuclear
cells from two healthy donors (10x Multiome gene expression, the openproblems
NeurIPS 2021 benchmark; the `s1d1`/`s1d3` samples of scanpy's clustering
tutorial). Measured 2026-10-14, isolated store seeded from the bundle,
`qc_filter` on `s1d1` with its raw asset's organism:

- `main` (`mouse`): 0 MT genes flagged, max 0.00% MT, 8,506 cells kept.
- Branch (`human`): 13 flagged, max 19.98%, 6,307 kept.
- The scRNA pipeline notebook exports with exit 0 and all 14 checks `ok`. Its
  page shows organism `human` 24 times, where the old bundle's showed `mouse`.
- Pinata's public metadata for both files updated to `organism: human`
  (merge; other keys unchanged), read back by a `bundle=scrna_demo` query.
- The catalog hook now runs on bundle YAML; it skipped the relabel before.

Deferred: ticket `qc-filter-organism-from-asset`.

## Outcome

Shipped in PR #33 (merged 2026-10-15). The `scrna_demo` bundle describes its
data as human bone marrow mononuclear cells and labels both files
`organism: human`, in the YAML and in Pinata's public metadata. The catalog
hook now also runs when a bundle's YAML changes.

Verified: `qc_filter` with the raw asset's organism flags 13 MT genes and
keeps 6,307 cells (0 and 8,506 on `main`); the scRNA pipeline notebook
exports with exit 0 and all 14 checks `ok`.

Left: ticket `qc-filter-organism-from-asset`.
