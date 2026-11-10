---
title: community-kernel-headers
status: doing
priority: normal
created: 2026-11-09
---

The community notebooks' headers, brought in line with ticket [[run-modes]]: a header lists what the notebook runs on this machine, an SDK task's packages and tools included. A PR in StargazerBio/community-notebooks, then the catalog's pins move to it.

- `scrna/clustering-pipeline.py` asks for `stargazer-bio[bio]`, an extra the package no longer has. It needs `scanpy` and `igraph` in its place, the packages its cells and the scRNA tasks import. Until then its "On this machine" runs fail with `No module named 'scanpy'` on an image built from `main` (inferred from the header and `pyproject.toml`, not driven).
- `germline/short-variant-discovery.py` keeps `gatk4`, `samtools` and `bwa-mem2`. A copy of it with that header ran the whole workflow "On this machine" in a hosted pod (measured in [[run-modes]]).
- Both install the SDK with `stargazer-bio = { path = "/stargazer", editable = true }`; the built-in notebooks' line has no `editable`. Both should list every package they import, `flyte` among them, as the built-in ones do.

Verify by opening each from the dashboard's catalog on an image built from `main` after PR 137, and running it "On this machine" and "On the cluster".

## Notes (2026-11-09)

Read at community-notebooks `b2197b2`, not driven. The scRNA notebook needs more than its header:

- It imports `scrna_env` from `stargazer.config`, which no longer has it (it's `stargazer.tasks.scrna.env` on `main`), so the notebook fails at import on an image from `main`.
- Its own tasks run on `pipeline_env`, cloned from `scrna_env` with `scrna_env.image.with_pip_packages("marimo>=0.23,<0.24")`: a hand-layered image, and a marimo range older than the image's 0.25.1. Under [[run-modes]] a notebook's own tasks build from its header with `notebook_image(__file__)`, so the header then lists what those tasks import (`scanpy`, `igraph`) as well.
- Its header lacks `flyte`, `scanpy` and `igraph`; the germline one lacks `flyte` only if it imports it (it doesn't today).

So the scRNA half is a small rewrite of its environment cell, to be verified "On this machine" and "On the cluster" from the catalog. Left in `next`.
- The germline notebook reads `cohort.sample_count`, which ticket [[provenance-on-every-output]] removes: use `len(cohort.source_samples)`.

Related: [[board]], [[run-modes]], [[community-catalog-pixi-headers]], [[marimo-autoadd-headers]], [[marimo-sandbox]].
