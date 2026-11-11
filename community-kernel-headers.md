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

PR 5 in StargazerBio/community-notebooks, on `fix/kernel-headers`. Each notebook run through marimo's kernel (`marimo export html`) in its header's pixi environment on macOS, SDK line pointed at a checkout of `main` (`ba777d4`), empty store, "On this machine" (all measured):

- scRNA: exit 0, both demo samples through all six stages (`s1d1` 6307 cells, `s1d3` 7157). The header also needed `scikit-image`: without it `qc_filter` fails in scrublet.
- Germline, started with `--run` on the demo inputs: exit 0, the cohort cell renders "1 sample(s) on GRCh38_TP53", cohort VCF 47 records.

"On the cluster", on the devbox, submitted from a checkout one run per task as the notebook's control does (measured): the scRNA notebook's own tasks ran on `stargazer-scrna-pipeline`, built from its header; `preprocess` (run `rh7l6wbtfdhnpxpfh52r`, 5 actions) returned the reduced AnnData (59 cells, 500 genes) and `cluster_and_annotate` (run `r8pntdzp4dkgmsvkg56z`, 3 actions) the annotated one. The germline notebook has no tasks of its own; its control submits the SDK workflow the devbox tier runs.

Not done: opening them from the dashboard's catalog in a hosted pod. A dashboard deploy isn't needed to check a notebook's own tasks; the recipe below drives them from a checkout. The catalog's pins move after the PR merges.

Gotchas: run as a script (`python notebook.py`), the scRNA notebook fails with `NameError: name 'preprocess' is not defined` (ticket [[script-mode-own-tasks]]); the kernel runs it. Running the environment's Python directly skips conda's activation, so `gatk` needs `JAVA_HOME=<env>/lib/jvm`.


## Verification recipe: a notebook's own tasks on the cluster

A notebook's own tasks run on an image built from its header, and the SDK tasks they call run in their own environments' pods.

### Driving it

Preconditions: the devbox up and set up, `FLYTE_IMAGE_REGISTRY=localhost:30000`, `kubectl port-forward -n flyte svc/rustfs-svc 9000:9000` open, the SDK checkout's root as cwd.

1. In an empty directory, copy the notebook to an importable name (`clustering_pipeline.py`) and add `seed_mod.py`, a task on the notebook's environment that stores an input from a `File`:

   ```python
   from pathlib import Path
   from flyte.io import File
   import clustering_pipeline as nb
   from stargazer.assets.scrna import AnnData
   from stargazer.utils.storage import get_client

   @nb.pipeline_env.task
   async def seed(raw_file: File, sample_id: str) -> AnnData:
       dest = get_client().local_dir / "raw.h5ad"
       dest.parent.mkdir(parents=True, exist_ok=True)
       await raw_file.download(str(dest))
       return await AnnData.store(dest, sample_id=sample_id, stage="raw", organism="human")
   ```

2. `drive.py` beside them puts the directory on `sys.path`, sets `FLYTE_DOCKER_BUILD_EXTRA_ARGS=--provenance=false`, calls `flyte.init_from_config(<checkout>/.flyte/config.yaml, root_dir=<the directory>)`, and submits each task as its own run with the devbox storage settings (`tests/devbox/conftest.py`'s `STORAGE`): `flyte.with_runcontext(env_vars=STORAGE).run(task, **inputs)`, then `wait()`, `raise_for_status()`, `outputs()[0]`. Seed `tests/fixtures/scrna/synthetic_200x500.h5ad` under a fresh sample ID, then `nb.preprocess(raw=..., max_pct_mt=80.0, n_top_genes=200)`, then `nb.cluster_and_annotate(reduced=..., resolution=1.0)`.
3. `pixi run python drive.py`. Passes: exit 0, `preprocess` returns stage `reduced` with 59 cells and 500 genes and its run has 5 actions, `cluster_and_annotate` returns stage `annotated` with `source_cid` set and its run has 3.

### Gotchas

- On `main` before ticket [[lean-task-bodies]] the seed task uses `default_client` and `AnnData().update(...)`.
- A notebook file with a hyphen in its name can't be imported by the driver; copy it under an underscore name.

Related: [[board]], [[run-modes]], [[community-catalog-pixi-headers]], [[marimo-autoadd-headers]], [[marimo-sandbox]], [[script-mode-own-tasks]], [[lean-task-bodies]].
