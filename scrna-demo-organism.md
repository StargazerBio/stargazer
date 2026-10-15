---
title: The scrna_demo bundle is labeled mouse but holds human data
status: doing
priority: normal
created: 2026-10-14
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
