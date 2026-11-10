---
title: community-kernel-headers
status: review
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


## Evidence (2026-11-10)

Draft PR 5 in StargazerBio/community-notebooks, on `fix/kernel-headers`. Each notebook run through marimo's kernel (`marimo export html`) in its header's pixi environment on macOS, SDK line pointed at a checkout of `main` (`ba777d4`), empty store, "On this machine" (all measured):

- scRNA: exit 0, both demo samples through all six stages (`s1d1` 6307 cells, `s1d3` 7157). The header also needed `scikit-image`: without it `qc_filter` fails in scrublet.
- Germline, started with `--run` on the demo inputs: exit 0, the cohort cell renders "1 sample(s) on GRCh38_TP53", cohort VCF 47 records.

Not done: "On the cluster" for either notebook, and opening them from the dashboard's catalog in a hosted pod, which is why the PR is a draft. The catalog's pins move after it merges.

Gotchas: run as a script (`python notebook.py`), the scRNA notebook fails with `NameError: name 'preprocess' is not defined` (ticket [[script-mode-own-tasks]]); the kernel runs it. Running the environment's Python directly skips conda's activation, so `gatk` needs `JAVA_HOME=<env>/lib/jvm`.

Related: [[board]], [[run-modes]], [[community-catalog-pixi-headers]], [[marimo-autoadd-headers]], [[marimo-sandbox]], [[script-mode-own-tasks]].
