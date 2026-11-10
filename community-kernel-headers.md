---
title: community-kernel-headers
status: next
priority: normal
created: 2026-11-09
---

The community notebooks' headers, brought in line with ticket [[run-modes]]: a header lists what the notebook runs on this machine, an SDK task's packages and tools included. A PR in StargazerBio/community-notebooks, then the catalog's pins move to it.

- `scrna/clustering-pipeline.py` asks for `stargazer-bio[bio]`, an extra the package no longer has. It needs `scanpy` and `igraph` in its place, the packages its cells and the scRNA tasks import. Until then its "On this machine" runs fail with `No module named 'scanpy'` on an image built from `main` (inferred from the header and `pyproject.toml`, not driven).
- `germline/short-variant-discovery.py` keeps `gatk4`, `samtools` and `bwa-mem2`. A copy of it with that header ran the whole workflow "On this machine" in a hosted pod (measured in [[run-modes]]).
- Both install the SDK with `stargazer-bio = { path = "/stargazer", editable = true }`; the built-in notebooks' line has no `editable`. Both should list every package they import, `flyte` among them, as the built-in ones do.

Verify by opening each from the dashboard's catalog on an image built from `main` after PR 137, and running it "On this machine" and "On the cluster".

Related: [[board]], [[run-modes]], [[community-catalog-pixi-headers]], [[marimo-autoadd-headers]], [[marimo-sandbox]].
