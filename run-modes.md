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

- [x] **`dispatch`:** "On this machine" is `flyte.with_runcontext(mode="local")`, for every task. `stargazer.notebooks.local_env` and its tests go, with the docker and pixi executors, the pickled call directories, the SDK overlay and the wrapped `LocalController.submit`. `build_image`, which the tasks tier still needs, moves into `cli/docker_task_tests.py`.
- [x] **Platforms:** the domain headers go back to `linux-64`, the platform their images run on, and their locks with them.
- [x] **Warm cache:** the image's warm-cache step also installs each domain's `env.py` header, so a notebook that lists gatk4 or scanpy builds its environment from local disk.
- [x] **Bundle root:** ticket `dispatch-installed-bundle`'s fix (PR 138) merges into this branch, since both rewrite `dispatch`.
- [x] **Docs:** the guide leads with the three sentences; `docs/architecture/notebook.md`, `configuration.md` and `runtime.md` for the mechanics.
- [x] **Verify:** a sandboxed notebook whose header lists a domain's packages runs an scRNA task and the germline workflow on this machine, in its kernel; a hosted pod does the same for a task whose tool its header lists.
      Done, with the hosted pod running the whole germline workflow: Evidence below.

Deferred:
- The community repo's headers: ticket [[community-kernel-headers]].
- Building a hosted notebook's environment into its pod image at launch, so it opens without installing: ticket [[prebuilt-notebook-environment]].

### Kept from the first version

- [x] **Template:** `my_env`, the environment the notebook's own tasks run on, builds from `flyte.Image.from_pixi_script(__file__)`. `main_env`, the pod's `AppEnvironment` on `notebook_base`, is unchanged. The header's `stargazer-bio` comes from `/stargazer`, which resolves only in a pod, so the build reads the header without that line and puts the SDK on top the way `task_image()` does: from a checkout (development), the checkout's source; from an installed package (production, a hosted pod included), the release of the kernel's version from PyPI. marimo's sandbox writes no lock, so the template's image is unlocked (the "your own risk" entry applies to it too).
      Done as `notebook_image()` in `config.py`; the basic template's `my_env` uses it. The build reads a copy of the header without its `[tool.pixi.pypi-dependencies]` `stargazer-bio` line, under `STARGAZER_LOCAL`; Flyte hashes the rendered manifest, so the kernel's and a pod's copies name the same image. Measured on local docker builds: the header as it was fails (`error while canonicalization /stargazer`); the checkout half builds and imports the template; the installed half builds with `stargazer-bio==2026.10.30` on top (that release predates `notebook_image`, so this branch's template can't import there, as expected). Both resolve flyte 2.13.0, unlocked.
- [x] **No core image:** every notebook's own tasks build from its header, the tutorials included, so there's one image rule for notebooks. `core_image()`, the published `stargazer-core` and its release wiring go; the tutorials' `tutorial_env` uses `notebook_image(__file__)`. A tutorial's first cluster run on a tenant builds its image once per release, cached by tag.
      Done: the Tasks tutorial's `tutorial_env` (imported by Workflows and Execution) uses `notebook_image(__file__, "stargazer-tutorial")`; `core_image()`, `_notebook_marimo()`, the `stargazer-core` publish and its release-workflow mention are gone; pyproject's `core` pixi environment, used only by `core_image()`, is removed and its entries cut from `pixi.lock` (the builder's pixi reads it as up to date; a full relock would have moved flyte to 2.13.0); `_with_source()` lost its `deps` flag. Docs, the wiki's `flyte-images` and AGENTS.md state one rule: an SDK task's image builds from its domain's `env.py` header, a notebook's own task's from the notebook's header. Measured: unit tier 283 passed; the tutorial's checkout image built locally and imports all three tutorials; from a hosted pod on the tenant (debug image), the Execution tutorial's `audit_cohorts` ran on the cluster (run `ulngbp5f75n9blfqwf6w`, SUCCEEDED, 3 `CohortSummary`) on `stargazer-tutorial-0997df0b…`, which Union's builder built from the tutorial's header in 1:01 with the installed release on top (PyPI 2026.10.30 here, as the image's version isn't released yet). `dispatch` "On the cluster" for the same workflow hits a bundling bug from main (ticket `dispatch-installed-bundle`), so the run went through `flyte.run`.

## Evidence

All on `feat/run-modes` at `b10ab00`, 2026-11-09: locally on osx-arm64 with pixi 0.84.1; the tenant as the test account, on `ghcr.io/stargazerbio/debug:run-modes-kernel` (`sha256:9774cbf3ce1bec205a1a2277228c59a02e71202bfa6f453d9788ebe01f08fdd9`). Measured unless it says otherwise.

- **Unit tier:** 280 passed. `test_an_sdk_task_on_this_machine_runs_in_the_kernel` and the `notebook_image` tests were each seen failing first.
- **Tasks tier:** gatk 20 passed, scrna 15 passed, on images `cli/docker_task_tests.py` now builds itself.
- **KERNEL-TASK, KERNEL-WORKFLOW:** the recipe's notebook in its header's own environment, exit 0 in 1:15. scanpy wasn't in `sys.modules` before the `normalize` dispatch and was loaded from the kernel's environment after it; `normalize: v1 normalized 59 500 bafybeigsvg…`; `germline: joint_call_gvcfs cohort-kernel ['NA12829'] bafkreifa3mox…`.
- **KERNEL-STORE:** `v1 shape True counts==input True X==log1p(normalize_total) True`; `cohort-kernel vcf samples ['NA12829'] == source True records 47 contigs ['chr17:7658421-7697490']`.
- **KERNEL-MISSING:** from a header with neither, `normalize` raised `RuntimeUserError ModuleNotFoundError: No module named 'scanpy'` and `samtools_faidx` raised `RuntimeUserError FileNotFoundError: [Errno 2] No such file or directory: 'samtools'`.
- **Warm cache:** the image is 2.17 GB against 1.35 GB for `debug:run-modes` (+0.82 GB), and `/opt/pixi-cache` 2.9 GB against 1.5 GB. `pixi install --script` of a header listing both domains' packages: 31 s and 45 conda packages fetched on the old image, 8 s and 3 fetched on the new one, both emulated amd64.
- **KERNEL-HOSTED:** the workspace notebook `germline-pixi-check`, whose header lists gatk4, samtools and bwa-mem2, opened in Edit on the debug image (the app's served image is the digest above; 1 CPU, 2Gi to 6Gi). With **On this machine**, build `GRCh38_TP53`, sample `NA12829` and cohort `kernel-hosted`, **Run the pipeline** returned "Cohort kernel-hosted: 1 sample(s) on GRCh38_TP53, VCF `bafkreidglsp6z7flklojph3gtwelcy437xpzhaxmwcmjtrz34b3v2hvtk4`" in about 41 s. The cell's log shows the run against `s3://stargazerbio-users` and the account's DSQL index, with `Running:` lines for samtools faidx, gatk CreateSequenceDictionary, bwa-mem2 index and mem, gatk SortSam, MarkDuplicates, HaplotypeCaller, GenomicsDBImport and GenotypeGVCFs. The results section rendered "47 sites across 1 sample(s)", the local run's count. The image has none of those tools on its `PATH` (`command -v` in the image finds none), so they came from the notebook's environment. The project's run list was the same three old runs before and after, so nothing went to the cluster.
- **Teardown:** dashboard redeployed on its release image, then `teardown` stopped `dashboard` and `nb-germline-pixi-check-edit`; live runs `[]`, no active app in `u-pryce`.
- **Not reached:** how long the hosted notebook takes to open from the warm cache. It opened in roughly 1.5 to 2 minutes including the pod's pull of the new image (rough); the pod's logs weren't read, as the AWS session had expired. The hosted VCF's file wasn't fetched and compared with its keyvalues; the check there is the rendered site count.

## Verification recipe: "On this machine" runs in the notebook's kernel

A notebook's header lists what it runs on this machine. `dispatch` set to "On this machine" runs an SDK task, or a workflow and every task it calls, in the kernel's process on what the header installed. A package or tool the header doesn't list fails with an error naming it.

### Sub-features

- **KERNEL-TASK**: an scRNA task dispatched "On this machine" returns its real output, with scanpy loaded in the kernel.
- **KERNEL-WORKFLOW**: the germline workflow dispatched "On this machine" returns the cohort's joint-called VCF, its tools the kernel environment's.
- **KERNEL-STORE**: the outputs are in the run's index and store, and their files hold what their keyvalues claim.
- **KERNEL-MISSING**: from a header without them, a task fails naming the missing package or tool.
- **KERNEL-HOSTED**: in a hosted pod, a notebook whose header lists a workflow's tools runs it "On this machine".

### How to get to it (user POV)

A notebook with `run_location()` in one cell and `await dispatch(where, <SDK task or workflow>, ...)` in another, the control on "On this machine", and the task's packages and tools in the header.

### Driving it

Preconditions: the repo root as cwd, pixi on the PATH, the run's isolated store exported (the `verify-stargazer` skill's Local notebook block) and `CO=$PWD`.

1. Write the notebook to `${RUN_DIR}/kernel.py`, its header pointing the SDK at the checkout:

   ```python
   # /// script
   # requires-python = ">=3.14"
   # dependencies = ["marimo", "stargazer-bio", "scanpy>=1.12", "igraph"]
   #
   # [tool.pixi.workspace]
   # channels = ["conda-forge", "bioconda"]
   #
   # [tool.pixi.dependencies]
   # python = "3.14.*"
   # gatk4 = "4.6.*"
   # samtools = "1.*"
   # bwa = "0.7.*"
   # bwa-mem2 = "2.*"
   #
   # [tool.pixi.pypi-dependencies]
   # stargazer-bio = { path = "<CO>", editable = true }
   # ///
   import marimo

   app = marimo.App(width="medium")

   with app.setup:
       import os, shutil, sys
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
       print("kernel:", sys.executable, "pid", os.getpid(), "stargazer:", stargazer.__file__)
       print("scanpy loaded before:", "scanpy" in sys.modules, "| kernel gatk:", shutil.which("gatk"))
       adata = AnnData(path=str(CHECKOUT / "tests/fixtures/scrna/qc_filtered.h5ad"), sample_id="v1", organism="human")
       norm = await dispatch(where, normalize, adata=adata)
       print("scanpy loaded after:", "scanpy" in sys.modules, "from", sys.modules["scanpy"].__file__)
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
       vcf = await dispatch(where, germline_short_variant_discovery, build="GRCh38", sample_ids=["NA12829"], cohort_id="cohort-kernel")
       print("germline:", vcf.caller, vcf.sample_id, vcf.source_samples, vcf.cid)
       return


   if __name__ == "__main__":
       app.run()
   ```

2. Run its cells in its header's environment (marimo's `export` takes no pixi sandbox; `pixi run --script` builds the same environment from the header): `pixi run --script "${RUN_DIR}/kernel.py" python "${RUN_DIR}/kernel.py" > "${RUN_DIR}/evidence/kernel.log" 2>&1`. Passes (KERNEL-TASK, KERNEL-WORKFLOW): exit 0; the log's kernel is under rattler's `cached-envs-v0`, its stargazer is `<CO>/src/stargazer`, `kernel gatk:` is a path in that environment, `scanpy loaded before: False`, `scanpy loaded after: True from` that environment, then `normalize: v1 normalized 59 500 …` and `germline: joint_call_gvcfs cohort-kernel ['NA12829'] …`.
3. KERNEL-STORE: list the run's records with the dev environment, and check the files with the notebook's environment's own Python, which has scanpy (`PY=$(ls -d ~/Library/Caches/rattler/cache/cached-envs-v0/kernel-*/envs/default/bin/python | head -1)`): `pixi run python "${RUN_DIR}/assemble.py" | grep -E "^(anndata|variants)" > "${RUN_DIR}/evidence/assembled.tsv"`, then `$PY "${RUN_DIR}/check.py" tests/fixtures/scrna/qc_filtered.h5ad "${RUN_DIR}/evidence/assembled.tsv"`.

   ```python
   # assemble.py: one TSV row per output
   import asyncio
   from stargazer.assets.asset import assemble
   async def main():
       for a in await assemble(asset="anndata", stage="normalized"):
           print("anndata", a.sample_id, a.n_obs, a.n_vars, a.cid, await a.fetch(), sep="\t")
       for v in await assemble(asset="variants", sample_id="cohort-kernel"):
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

   Passes: `v1 shape True counts==input True X==log1p(normalize_total) True` and `cohort-kernel vcf samples ['NA12829'] == source True records 47 contigs ['chr17:7658421-7697490']`.
4. KERNEL-MISSING: a second notebook, `${RUN_DIR}/missing.py`, with the same header minus scanpy, igraph and the four tools, run the same way into a second store (`STARGAZER_LOCAL`, `STARGAZER_STORE_ROOT` and `STARGAZER_INDEX_URL` pointed at fresh paths). Its setup imports `normalize` and `samtools_faidx`, and its one cell is:

   ```python
   for task, inputs in (
       (normalize, {"adata": AnnData(path=str(CHECKOUT / "tests/fixtures/scrna/qc_filtered.h5ad"), sample_id="v1", organism="human")}),
       (samtools_faidx, None),
   ):
       if inputs is None:
           fa = Path(os.environ["STARGAZER_LOCAL"]) / "tiny.fa"; fa.parent.mkdir(parents=True, exist_ok=True)
           fa.write_text(">chrT\nACGTACGTAC\nGTACGTACGT\n")
           ref = Reference(build="tiny"); await ref.update(fa)
           inputs = {"ref": ref}
       try:
           await dispatch(where, task, **inputs)
       except Exception as e:
           print("MISSING", task.name, type(e).__name__, str(e)[:200].replace("\n", " "))
   ```

   Passes: `MISSING … RuntimeUserError ModuleNotFoundError: No module named 'scanpy'` and `MISSING gatk.samtools_faidx RuntimeUserError FileNotFoundError: [Errno 2] No such file or directory: 'samtools'`.
5. Warm cache: build the branch's image for amd64 and push it to `ghcr.io/stargazerbio/debug:<slug>`. In it and in the image it's compared with, copy a notebook whose header is step 1's with `stargazer-bio = { path = "/stargazer" }` to `/tmp/w/both.py`, then time `pixi install --script /tmp/w/both.py` and count the entries added to `/opt/pixi-cache/pkgs`. Passes: a handful of packages fetched, against dozens without the domains in the cache.
6. KERNEL-HOSTED: deploy the test account's dashboard on the debug image (infra's `verify-dashboard` skill). The account's workspace holds `germline-pixi-check`, a germline notebook whose header lists gatk4, samtools and bwa-mem2, and its store holds build `GRCh38_TP53` and sample `NA12829`. Open it in **Edit**, pick **On this machine**, the build, the sample and a fresh cohort name, and press **Run the pipeline**. Passes: the cell reports the cohort with a VCF CID, its log shows `Running:` lines for each tool, and the results section counts 47 sites across 1 sample. `union_dashboard.py check nb-germline-pixi-check-edit` before and after lists the same runs. Then redeploy the dashboard without `STARGAZER_NOTEBOOK_IMAGE`, run `union_dashboard.py teardown`, and confirm no active app and live runs `[]`.

### Gotchas

- `pixi run --script X python Y` runs X's environment but, for a marimo notebook X, re-ran X rather than Y. Run a second script with the environment's own Python from rattler's `cached-envs-v0`. A second run of the workflow stores a second VCF under the same cohort, with its own CID.
- marimo's `export` has no pixi sandbox (`--sandbox` is uv's only), so step 2 runs the notebook's cells with `pixi run --script`, which builds the header's environment as the sandbox does.
- The domain headers lock for `linux-64` only, so the image's warm cache holds their packages in its amd64 build alone. Measure the cache on that build.
- In the built-in browser, marimo's page shifts after it's measured: click a button at the coordinates of a fresh screenshot, not by an element reference found earlier.
- A workspace notebook with no pixi Python pin never starts its kernel on a pixi-sandbox image (ticket `unpinned-notebook-python`); `germline-pixi-check` has the pin.
- Byte-identical outputs share a CID, and the index keeps one record per CID: use distinct inputs per sample.

## Run modes today

Callers:

| Caller | Kernel environment | Where tasks run |
|---|---|---|
| Script or IDE from a checkout (`pixi run`) | dev env, editable SDK | in-process, or cluster on images built from source |
| Script with `stargazer-bio` installed in your own env | your env | in-process, or cluster on the release's images |
| Notebook locally, `pixi run marimo edit` | dev env | in the kernel, or cluster |
| Notebook locally, sandboxed | its header | in the kernel, or cluster |
| Notebook in the stargazer image, `docker run` | its header | in the kernel only |
| Notebook hosted | its header | in the kernel, or cluster |
| MCP agent (local, or the pod's terminal) | the `mcp` env, editable | cluster, images built from source |
| A workflow's pod | its task image | children in their own pods |

Executors: in-process (Flyte local mode), a Union pod, a devbox pod.

Related: [[board]], [[local-runs-in-task-image]], [[hosted-local-runs]], [[dispatch-installed-bundle]], [[released-sdk-in-notebooks]], [[notebook-image-digest]], [[marimo-autoadd-headers]], [[pixi-notebook-sandbox]], [[flyte-images]], [[marimo-sandbox]].
