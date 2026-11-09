---
title: run-modes
status: review
priority: normal
created: 2026-11-09
pr: 137
---

Stargazer code runs from a script, a notebook (locally, in the stargazer image under docker, or hosted), the MCP agent, or a workflow's pod, and a task's body runs in-process, in its image under docker, or in a cluster pod (Union or the devbox). Which packages each of those needs is hard to explain today: a notebook's header lists a domain's tools only so "On this machine" can run SDK tasks in the kernel, and a notebook's own tasks get their packages from image layers the author adds by hand, beside the header. This ticket settles one happy path that fits in three sentences, conventions for the SDK, and a "your own risk" zone for everything else.

## The happy path

1. **An environment is a header.** A PEP 723 block that pixi installs. A domain has one, in `tasks/<domain>/env.py`, locked and published as an image with each release. A notebook has one, at its top, which marimo writes as you import.
2. **On this machine, everything runs in the notebook's kernel**, so the header lists what you run here: your cells' packages, and the packages and tools of any SDK task you run here.
3. **On the cluster, each task runs in its environment's image**: an SDK task in its domain's, the notebook's own tasks in one built from the notebook's header. A cluster run of an SDK task needs nothing in the header, since a domain's packages import inside its task bodies.

So "On this machine" is Flyte's local mode and nothing more, and one header is both the place a task's packages are listed and the source of its image: `task_image(__file__)` builds an SDK task image with `flyte.Image.from_pixi_script` on its `env.py`, and `notebook_image(__file__)` a notebook's.

The first version of this ticket had a fourth rule, that calling an SDK task from a notebook needs nothing in the header even on this machine, and kept it by running each SDK task in its domain's environment as a subprocess (pixi, or the task image under docker). It was built, measured and then removed: it took a 434-line module, two executors, a patched Flyte local controller and `osx-arm64` in both domain locks to save a notebook three header lines, and the notebooks that run SDK tasks import the same packages in their own cells anyway.

## Conventions

- **SDK:** every `TaskEnvironment` under `stargazer.tasks` builds with `task_image(__file__)` from its own `env.py` (AGENTS.md already says so). A domain's packages are listed only in its header and imported inside task bodies. This stays a written convention, reviewed in PRs: no test or lint enforces it, since the shape may still change.
- **Notebook authors:** anything goes. The template shows the happy path.

## Your own risk

Supported, not the happy path:
- Any other `flyte.Image` on a notebook's own `TaskEnvironment` (`from_base`, hand-added layers, anything).
- An unlocked notebook header, whose cluster image can resolve differently between builds. The run records the image's digest (ticket `notebook-image-digest`), but the header alone doesn't reproduce it.
- An SDK task run on this machine uses the header's versions of its tools, not its domain's lock. The cluster run is the reproducible one.
- A tool with no build for your machine (some of bioconda on Apple silicon): run it on the cluster, or open the notebook in the Stargazer image.

## Plan

Built on `feat/run-modes`, cut from `main` after PR 134 (the docker path) merged, which it removes.

### On this machine runs in the kernel

- [ ] **`dispatch`:** "On this machine" is `flyte.with_runcontext(mode="local")`, for every task. `stargazer.notebooks.local_env` and its tests go, with the docker and pixi executors, the pickled call directories, the SDK overlay and the wrapped `LocalController.submit`. `build_image`, which the tasks tier still needs, moves into `cli/docker_task_tests.py`.
- [ ] **Platforms:** the domain headers go back to `linux-64`, the platform their images run on, and their locks with them.
- [ ] **Warm cache:** the image's warm-cache step also installs each domain's `env.py` header, so a notebook that lists gatk4 or scanpy builds its environment from local disk.
- [ ] **Bundle root:** ticket `dispatch-installed-bundle`'s fix (PR 138) merges into this branch, since both rewrite `dispatch`.
- [ ] **Docs:** the guide leads with the three sentences; `docs/architecture/notebook.md`, `configuration.md` and `runtime.md` for the mechanics.
- [ ] **Verify:** a sandboxed notebook whose header lists a domain's packages runs an scRNA task and the germline workflow on this machine, in its kernel; a hosted pod does the same for a task whose tool its header lists.

Deferred:
- The community repo's headers, a PR in StargazerBio/community-notebooks: the germline notebook keeps its tools; the scRNA one asks for `stargazer-bio[bio]`, an extra that's gone, and needs `scanpy` in its place.
- Building a hosted notebook's environment into its pod image at launch, so it opens without installing (infra; depends on ticket `layered-notebook-image-cache`).

### Kept from the first version

- [x] **Template:** `my_env`, the environment the notebook's own tasks run on, builds from `flyte.Image.from_pixi_script(__file__)`. `main_env`, the pod's `AppEnvironment` on `notebook_base`, is unchanged. The header's `stargazer-bio` comes from `/stargazer`, which resolves only in a pod, so the build reads the header without that line and puts the SDK on top the way `task_image()` does: from a checkout (development), the checkout's source; from an installed package (production, a hosted pod included), the release of the kernel's version from PyPI. marimo's sandbox writes no lock, so the template's image is unlocked (the "your own risk" entry applies to it too).
      Done as `notebook_image()` in `config.py`; the basic template's `my_env` uses it. The build reads a copy of the header without its `[tool.pixi.pypi-dependencies]` `stargazer-bio` line, under `STARGAZER_LOCAL`; Flyte hashes the rendered manifest, so the kernel's and a pod's copies name the same image. Measured on local docker builds: the header as it was fails (`error while canonicalization /stargazer`); the checkout half builds and imports the template; the installed half builds with `stargazer-bio==2026.10.30` on top (that release predates `notebook_image`, so this branch's template can't import there, as expected). Both resolve flyte 2.13.0, unlocked.
- [x] **No core image:** every notebook's own tasks build from its header, the tutorials included, so there's one image rule for notebooks. `core_image()`, the published `stargazer-core` and its release wiring go; the tutorials' `tutorial_env` uses `notebook_image(__file__)`. A tutorial's first cluster run on a tenant builds its image once per release, cached by tag.
      Done: the Tasks tutorial's `tutorial_env` (imported by Workflows and Execution) uses `notebook_image(__file__, "stargazer-tutorial")`; `core_image()`, `_notebook_marimo()`, the `stargazer-core` publish and its release-workflow mention are gone; pyproject's `core` pixi environment, used only by `core_image()`, is removed and its entries cut from `pixi.lock` (the builder's pixi reads it as up to date; a full relock would have moved flyte to 2.13.0); `_with_source()` lost its `deps` flag. Docs, the wiki's `flyte-images` and AGENTS.md state one rule: an SDK task's image builds from its domain's `env.py` header, a notebook's own task's from the notebook's header. Measured: unit tier 283 passed; the tutorial's checkout image built locally and imports all three tutorials; from a hosted pod on the tenant (debug image), the Execution tutorial's `audit_cohorts` ran on the cluster (run `ulngbp5f75n9blfqwf6w`, SUCCEEDED, 3 `CohortSummary`) on `stargazer-tutorial-0997df0b…`, which Union's builder built from the tutorial's header in 1:01 with the installed release on top (PyPI 2026.10.30 here, as the image's version isn't released yet). `dispatch` "On the cluster" for the same workflow hits a bundling bug from main (ticket `dispatch-installed-bundle`), so the run went through `flyte.run`.

## Evidence

All on `feat/run-modes`, 2026-11-09, osx-arm64 with docker 29.8.2 and pixi 0.84.1 locally; the tenant as the test account.

- **Unit tier:** passes, with `tests/notebooks/test_local_env.py` (routing, env lookup, workspace, overlay, workflows) and `tests/unit/test_task_images.py` (`notebook_image`), each test seen failing first.
- **Docker fallback:** with the headers on `linux-64` only, `normalize` ran in its image under docker and returned a 59×500 normalized AnnData.
- **pixi "Here":** `normalize` installed scrna's environment in 54 s the first time, then ran in 7 s.
- **Sandboxed notebook, local:** the recipe below, run in the header's own environment (`pixi run --script`), 118 s: the kernel was the header's, with the checkout's SDK and neither scanpy nor gatk; `normalize` returned `v1 normalized 59 500`; the germline workflow returned the joint-called `cohort-here` VCF. Stored outputs: the AnnData's shape, raw counts and `log1p(normalize_total)` values check out against the input; the VCF calls `NA12829`, 47 records on `chr17:7658421-7697490`. With `normalize`'s stage changed in the checkout, the rerun returned `stage=normalized_here_edit`.
- **Hosted pod:** the Tasks tutorial in edit mode on `ghcr.io/stargazerbio/debug:run-modes` (pod and dashboard both): `dispatch(where, samtools_faidx, ...)` "On this machine" from a kernel with no samtools installed gatk's environment in the pod (`envs ['gatk']`) and stored `run_modes_tiny.fa.fai` in the test account's S3 store, reading `chrT\t20\t6\t10\t11`. Torn down after: no active app in `u-pryce`, no live runs; the dashboard redeployed on its release first.
- **Tasks tier:** gatk and scrna images rebuilt from the relocked headers (see the PR).
- **After merging `main` (#135):** unit tier 284 passed, tasks tier passed, local `normalize` "Here" returned the same CID, the template's checkout image rebuilt and imports the template, and the hosted check passed again on the rebuilt image with the kernel's SDK now an installed package. `notebook_image()` keeps `stargazer-bio==<version>` on top when installed: `from_pixi_script` can't start from the published `stargazer-core`, which lacks the header's packages anyway.
- **Not covered:** a workspace notebook created from the release dashboard's Blank seed can't start its kernel on the new image (ticket `unpinned-notebook-python`), so the hosted check used a built-in notebook.

## Verification recipe: SDK tasks and workflows run "Here" in their own environments

A notebook calling SDK tasks lists none of their domain packages: "On this machine" runs each task in its domain's environment, installed with pixi from the domain's `env.py` header and lock, and an SDK workflow's body in the kernel with each task in its own environment. The task runs the kernel's own SDK, so a checkout's edits show up.

### Sub-features

- **HERE-TASK**: an scRNA task dispatched "On this machine" returns its real output from a kernel without scanpy.
- **HERE-WORKFLOW**: the germline workflow dispatched "On this machine" returns the cohort's joint-called VCF from a kernel without gatk.
- **HERE-EDIT**: an edit to a task in the checkout shows in the next run's output.
- **HERE-STORE**: the outputs are in the run's index and store, and their files hold what their keyvalues claim.
- **HERE-HOSTED**: in a hosted pod, a package task dispatched "On this machine" installs its environment in the pod and returns its output.

### How to get to it (user POV)

A notebook with `run_location()` in one cell and `await dispatch(where, <SDK task or workflow>, ...)` in another, the control on "On this machine".

### Driving it

Preconditions: the repo root as cwd, pixi on the PATH, the run's isolated store exported (the `verify-stargazer` skill's Local notebook block) and `CO=$PWD`.

1. Write the notebook to `${RUN_DIR}/here.py`, its header pointing the SDK at the checkout:

   ```python
   # /// script
   # requires-python = ">=3.14"
   # dependencies = ["marimo", "stargazer-bio"]
   #
   # [tool.pixi.dependencies]
   # python = "3.14.*"
   #
   # [tool.pixi.pypi-dependencies]
   # stargazer-bio = { path = "<CO>", editable = true }
   # ///
   import marimo

   app = marimo.App(width="medium")

   with app.setup:
       import importlib.util, os, shutil, sys
       from pathlib import Path
       import stargazer
       from stargazer.assets import R1, R2, Reference
       from stargazer.assets.scrna import AnnData
       from stargazer.config import init_flyte
       from stargazer.notebooks.ui import dispatch, run_location
       from stargazer.tasks.scrna.normalize import normalize
       from stargazer.workflows import germline_short_variant_discovery

       init_flyte()
       CHECKOUT = Path("<CO>")


   @app.cell
   def _():
       where = run_location()
       where
       return (where,)


   @app.cell
   async def _(where):
       print("kernel:", sys.executable, "stargazer:", stargazer.__file__)
       print("kernel has scanpy:", importlib.util.find_spec("scanpy") is not None, "gatk:", shutil.which("gatk"))
       adata = AnnData(path=str(CHECKOUT / "tests/fixtures/scrna/qc_filtered.h5ad"), sample_id="v1", organism="human")
       norm = await dispatch(where, normalize, adata=adata)
       print("normalize:", norm.sample_id, norm.stage, norm.n_obs, norm.n_vars, norm.cid)
       return


   @app.cell
   async def _(where):
       local = Path(os.environ["STARGAZER_LOCAL"]); local.mkdir(parents=True, exist_ok=True)
       for name in ("GRCh38_TP53.fa", "NA12829_TP53_R1.fq.gz", "NA12829_TP53_R2.fq.gz"):
           shutil.copy(CHECKOUT / "tests/fixtures/general" / name, local / name)
       ref = Reference(build="GRCh38"); await ref.update(local / "GRCh38_TP53.fa")
       r1, r2 = R1(sample_id="NA12829"), R2(sample_id="NA12829")
       await r1.update(local / "NA12829_TP53_R1.fq.gz")
       await r2.update(local / "NA12829_TP53_R2.fq.gz", mate_cid=r1.cid)
       await r1.update(local / "NA12829_TP53_R1.fq.gz", mate_cid=r2.cid)
       vcf = await dispatch(where, germline_short_variant_discovery, build="GRCh38", sample_ids=["NA12829"], cohort_id="cohort-here")
       print("germline:", vcf.caller, vcf.sample_id, vcf.source_samples, vcf.cid)
       return


   if __name__ == "__main__":
       app.run()
   ```

2. Run its cells in its header's environment (marimo's `export` takes no pixi sandbox; `pixi run --script` builds the same environment from the header): `pixi run --script "${RUN_DIR}/here.py" python "${RUN_DIR}/here.py" > "${RUN_DIR}/evidence/plain.log" 2>&1`. Passes (HERE-TASK, HERE-WORKFLOW): exit 0; the log's kernel is under rattler's `cached-envs-v0`, its stargazer is `<CO>/src/stargazer`, `kernel has scanpy: False gatk: None`, then `normalize: v1 normalized 59 500 …` and `germline: joint_call_gvcfs cohort-here ['NA12829'] …`.
3. HERE-EDIT: `sed -i '' 's/stage="normalized")/stage="normalized_here_edit")/' src/stargazer/tasks/scrna/normalize.py`, rerun step 2 into a fresh store, then `git checkout -- src/stargazer/tasks/scrna/normalize.py`. Passes: `normalize: v1 normalized_here_edit 59 500`.
4. HERE-STORE: list the run's records and check the files, the AnnData in the run's own scrna environment (`${STARGAZER_LOCAL}/envs/scrna/.pixi/envs/default/bin/python`):

   ```python
   # assemble.py: one TSV row per output
   import asyncio
   from stargazer.assets.asset import assemble
   async def main():
       for a in await assemble(asset="anndata", stage="normalized"):
           print("anndata", a.sample_id, a.n_obs, a.n_vars, a.cid, await a.fetch(), sep="\t")
       for v in await assemble(asset="variants", sample_id="cohort-here"):
           print("variants", v.sample_id, ",".join(v.source_samples), v.caller, v.cid, await v.fetch(), sep="\t")
   asyncio.run(main())
   ```

   ```python
   # check.py <input h5ad> <assembled.tsv>
   import sys
   import numpy as np, scanpy as sc, scipy.sparse as sp
   dense = lambda m: m.toarray() if sp.issparse(m) else np.asarray(m)
   for line in open(sys.argv[2]):
       kind, *f = line.rstrip("\n").split("\t")
       if kind == "anndata":
           sample, n_obs, n_vars, cid, path = f
           out, raw = sc.read_h5ad(path), sc.read_h5ad(sys.argv[1])
           counts = dense(out.layers["counts"])
           expect = sc.AnnData(counts.copy()); sc.pp.normalize_total(expect); sc.pp.log1p(expect)
           print(sample, "shape", out.shape == (int(n_obs), int(n_vars)), "counts==input", np.array_equal(counts, dense(raw.X)), "X==log1p(normalize_total)", np.allclose(dense(out.X), dense(expect.X)))
       else:
           sample, sources, caller, cid, path = f
           lines = open(path).read().splitlines()
           header = next(l for l in lines if l.startswith("#CHROM")).split("\t")[9:]
           recs = [l.split("\t") for l in lines if l and not l.startswith("#")]
           print(sample, "vcf samples", header, "== source", header == sources.split(","), "records", len(recs), "contigs", sorted({r[0] for r in recs}))
   ```

   Passes: `v1 shape True counts==input True X==log1p(normalize_total) True` and `cohort-here vcf samples ['NA12829'] == source True records 47 contigs ['chr17:7658421-7697490']`; no `env-run-*` left in `$STARGAZER_LOCAL`.
5. HERE-HOSTED: build the branch's image and push it to `ghcr.io/stargazerbio/debug:<slug>`, deploy the test account's dashboard on it (infra's `verify-dashboard` skill), launch a built-in notebook in edit mode (`POST /launch` with `slug=tasks`, `mode=edit`, `section=tutorials`), and add two cells at its end:

   ```python
   from stargazer.notebooks.ui import dispatch, run_location; where = run_location(); where
   ```

   ```python
   import os, shutil, sys, stargazer; from pathlib import Path; from stargazer.assets import Reference; from stargazer.tasks.general.samtools import samtools_faidx; _fa = Path(os.environ["STARGAZER_LOCAL"]) / "run_modes_tiny.fa"; _fa.parent.mkdir(parents=True, exist_ok=True); _fa.write_text(">chrT\nACGTACGTAC\nGTACGTACGT\n"); _ref = Reference(build="run-modes-tiny"); await _ref.update(_fa); _idx = await dispatch(where, samtools_faidx, ref=_ref); print("RESULT kernel", sys.executable, "| stargazer", stargazer.__file__, "| kernel samtools", shutil.which("samtools"), "| envs", sorted(os.listdir(Path(os.environ["STARGAZER_LOCAL"]) / "envs")), "| fai", _idx.path.path, "=", repr(Path(await _idx.fetch()).read_text()))
   ```

   Passes: `kernel samtools None | envs ['gatk'] | fai s3://…/run_modes_tiny.fa.fai = 'chrT\t20\t6\t10\t11\n'`. Then redeploy the dashboard on its release, `union_dashboard.py teardown`, deactivate the dashboard, and confirm no active app and no live run.

### Gotchas

- A pixi environment can't be moved or copied between run directories: pixi refuses it as non-relocatable. Let each run install its own; pixi's package cache makes the second install quick.
- marimo's `export` has no pixi sandbox (`--sandbox` is uv's only), so step 2 runs the notebook's cells with `pixi run --script`, which builds the header's environment as the sandbox does.
- A workspace notebook created from the release dashboard's Blank seed has no pixi Python pin and its kernel never starts on a pixi-sandbox image (ticket `unpinned-notebook-python`); use a built-in notebook for HERE-HOSTED.
- In the hosted editor, a second browser tab connects as a reader and its cells stay queued; take over the session first. A built-in notebook's added cells aren't saved, so they're gone after a takeover.
- Byte-identical outputs share a CID, and the index keeps one record per CID: use distinct inputs per sample.

## Run modes today

For reference while planning. Callers:

| Caller | Kernel environment | Where tasks run |
|---|---|---|
| Script or IDE from a checkout (`pixi run`) | dev env, editable SDK | in-process, or cluster on images built from source |
| Script with `stargazer-bio` installed in your own env | your env | in-process, or cluster on the release's images |
| Notebook locally, `pixi run marimo edit` | dev env | in-process, docker (PR 134), or cluster |
| Notebook locally, sandboxed | its header | in-process, docker (PR 134), or cluster |
| Notebook in the stargazer image, `docker run` | its header | in-process only |
| Notebook hosted | its header | in-process, or cluster |
| MCP agent (local, or the pod's terminal) | the `mcp` env, editable | cluster, images built from source |
| A workflow's pod | its task image | children in their own pods |

Executors: in-process (Flyte local mode), the task image under local docker, a Union pod, a devbox pod.

Related: [[board]], [[local-runs-in-task-image]], [[hosted-local-runs]], [[released-sdk-in-notebooks]], [[notebook-image-digest]], [[marimo-autoadd-headers]], [[pixi-notebook-sandbox]], [[flyte-images]], [[marimo-sandbox]].
