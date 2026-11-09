---
title: local-runs-in-task-image
status: done
priority: normal
created: 2026-11-04
pr: 134
---

A notebook's **On this machine** runs a domain's tasks inside the kernel, so the notebook's own header has to list the domain's packages: scanpy's stack for scRNA, and gatk4, samtools and bwa-mem2 for germline. The task's environment already declares those packages in its domain's `env.py` header. Running the task in its own image, under docker, would mean no notebook ever installs a domain's packages, and the local run would be the same environment as the cluster run.

## Answers

- **Flyte 2 can't run a task in its container locally.** Measured on `flyte` 2.12.4: `Mode` in `flyte/_run.py` is `local`, `remote` or `hybrid`, and the local controller (`flyte/_internal/controllers/_local_controller.py`) runs every task through `direct_dispatch`, in the calling process. `with_runcontext(mode="local").run(normalize, ...)` from the dev environment fails with `ModuleNotFoundError: No module named 'scanpy'`. The pod entrypoint (`flyte/_bin/runtime.py`'s `a0`) can't stand in either: it calls `init_in_cluster` and makes a remote controller. So `dispatch` runs the container itself, the way `cli/docker_task_tests.py` runs the tasks tier.
- **The container is the task's own image, running the task in Flyte's local mode.** Prototyped by hand 2026-11-07 on osx-arm64, docker 29.8.2: the checkout's `stargazer-scrna` built in 69 s (cached base layers); `normalize` on `qc_filtered.h5ad`, its input pickled into a directory both sides see, ran in `docker run --platform linux/amd64 --user <uid>:<gid> -e HOME=/tmp`, with `STARGAZER_LOCAL`, `STARGAZER_STORE_ROOT` and the SQLite index's directory bind-mounted at their host paths. 18.4 s wall, emulated. The pickled output came back as a real `AnnData` with its cid, its file in the host's store and its row in the host's index, owned by the host user.
- **A hosted pod has no docker.** Measured: the notebook image (`ghcr.io/stargazerbio/debug:notebook-dockerignore`) has no `docker` binary and no `/var/run/docker.sock`, and a pod gets no daemon. There, "On this machine" keeps running in the kernel, as it does today, so a hosted notebook that runs a package task on this machine still needs its domain's packages in its header. Whether a pod should instead send package tasks to the cluster is its own decision: ticket `hosted-local-runs`.
- **Apple silicon** runs the amd64 images emulated, as the prototype did. GenomicsDB's joint calling isn't measured here.

## Plan

One case first: `marimo edit` from a checkout, docker on the PATH, dispatching a package task (one whose module is in `stargazer.tasks` or `stargazer.workflows`) on this machine.

- [x] `stargazer.notebooks.local_image`: `runs_in_image(task)` (docker on the PATH, a package task, a `flyte.Image`); `build_image(image)`, moved from `cli/docker_task_tests.py`, which imports it; `run_in_image(task, inputs)`, which pickles the inputs into a call directory under `STARGAZER_LOCAL`, runs `python -m stargazer.notebooks.local_image` in the task's image with the store, the index's directory, `STARGAZER_LOCAL` and each input asset's directory (read-only) mounted at their host paths, the storage and Pinata variables passed through, and returns the unpickled output; a failed run raises with the container's output. Its container side imports the task by module and name and runs it with Flyte's local mode.
- [x] `dispatch`'s local branch calls `run_in_image` when `runs_in_image(task)`, else runs in-process as before.
- [x] Unit tests in `tests/notebooks/`: the routing (package task with docker → image; no docker, or a notebook's task → in-process) and the mounts.
- [x] Docs: `docs/architecture/notebook.md` (Execution Context, Boundary rules), `ui.py`'s docstring, and the [[flyte]] wiki page's Running tasks (no local container mode).
- [x] Verified in a notebook whose header has no scanpy, dispatching scRNA's `normalize` on this machine.

Later, each its own change:
- [ ] A hosted pod's "On this machine" for package tasks (ticket `hosted-local-runs`).
- [ ] A notebook's own `@app.function` tasks in their image, which needs the notebook mounted as their code.
- [ ] An installed package pulling its release's images (`released_image()`) rather than building.
- [ ] The germline workflow on Apple silicon: emulated GenomicsDB, timed.

## Evidence

Measured 2026-11-07 on osx-arm64, docker 29.8.2, at `9f7a97e` (PR #134):
- The recipe's notebook exported with exit 0 in 15 s from the dev environment, which has no scanpy (`find_spec('scanpy')` is `None`; the log reads `kernel has scanpy: False`). It returned `AnnData v1 normalized 59 500` and `AnnData v2 normalized 200 500`, stored under the run's store. On a fresh source, the gathered pair built the image once.
- `assemble()` from the run's index found both records, and in the scrna image both read `shape True counts==input True X==log1p(normalize_total) True`.
- Failure path: `FileNotFoundError: /nonexistent/x.h5ad doesn't exist and has no CID` and `OSError: Unable to synchronously open file (file signature not found)`, each inside `scrna.normalize failed in stargazer-scrna:<hash> (exit 1)`, and no call directory left behind.
- Unit tier passes; tasks tier gatk 20 passed and scrna 15 passed.

## Native environments, measured first

Measured 2026-11-04 on osx-arm64 with pixi 0.84.1, using a copy of `tasks/scrna/env.py`'s header:
- As written, `pixi install --script` refuses, because the header lists only `linux-64`.
- With `osx-arm64` added to the header's platforms, it solves and installs in 23 s, and scanpy 1.12.5 imports. The SDK it carries is the released `stargazer-bio` from PyPI, so the checkout goes on top with `PYTHONPATH=src`.
- With pytest and pytest-asyncio added to that environment via `uv pip`, `PYTHONPATH=src python -m pytest -m tasks tests/tasks/scrna` passed 14 of 15 in 42 s. `test_sample_isolation.py::test_parallel_samples_write_distinct_files[normalize]` failed once and passed 6 of 6 when rerun alone.

So for scRNA, a native run needs `osx-arm64` in the header (and a lock for it) and a supported way to add the checkout and the test tools. Docker isn't needed. The gatk header is the hard case: GenomicsDB is x86_64 only.

## Verification recipe: package tasks on this machine run in their image

A notebook opened from a checkout, with docker running, dispatches a package task "On this machine": the task runs in its own task image, the notebook's environment has none of the domain's packages, and the output comes back as the real asset, stored in the notebook's own local store and index.

### Sub-features

- **IMG-RUN**: `dispatch(run_location(), normalize, ...)` returns a normalized `AnnData` while the kernel has no scanpy.
- **IMG-GATHER**: two samples dispatched with `asyncio.gather` build the image once and both come back.
- **IMG-STORE**: the outputs are in the run's index and store at host paths, and their files hold what their keyvalues claim.
- **IMG-FAIL**: a task that fails in the container raises `RuntimeError` naming the task, the image and the task's own error, and leaves no call directory behind.

### How to get to it (user POV)

`pixi run marimo edit <notebook>` from a checkout, a cell with `run_location()`, another with `await dispatch(where, <package task>, ...)`, the control left on "On this machine".

### Driving it

Preconditions: docker running, the repo root as cwd, the run's isolated store exported (the `verify-stargazer` skill's Local notebook block). In zsh, brace `${RUN_DIR}` before a `:ro` suffix: `$RUN_DIR:r` is a modifier.

1. Write this notebook to `${RUN_DIR}/scrna_here.py`. Its header has no scanpy, and the dev environment it runs in has none either (`pixi run python -c "import importlib.util; print(importlib.util.find_spec('scanpy'))"` prints `None`).

   ```python
   # /// script
   # requires-python = ">=3.14"
   # dependencies = ["marimo", "stargazer-bio"]
   #
   # [tool.pixi.dependencies]
   # python = "3.14.*"
   # ///
   import marimo

   app = marimo.App(width="medium")

   with app.setup:
       import asyncio
       import importlib.util
       from pathlib import Path

       import marimo as mo

       from stargazer.assets.scrna import AnnData
       from stargazer.config import init_flyte
       from stargazer.notebooks.ui import dispatch, run_location
       from stargazer.tasks.scrna.normalize import normalize

       init_flyte()
       FIXTURES = {
           s: str(Path.cwd() / "tests/fixtures/scrna" / f)
           for s, f in (("v1", "qc_filtered.h5ad"), ("v2", "synthetic_200x500.h5ad"))
       }


   @app.cell
   def _():
       where = run_location()
       where
       return (where,)


   @app.cell
   async def _(where):
       samples = [AnnData(path=p, sample_id=s, organism="human") for s, p in FIXTURES.items()]
       results = await asyncio.gather(*[dispatch(where, normalize, adata=a) for a in samples])
       print("kernel has scanpy:", importlib.util.find_spec("scanpy") is not None)
       for r in results:
           print(type(r).__name__, r.sample_id, r.stage, r.n_obs, r.n_vars, r.cid, r.path.path)
       mo.md(f"normalized {len(results)} samples")
       return


   if __name__ == "__main__":
       app.run()
   ```

2. `pixi run marimo export html "${RUN_DIR}/scrna_here.py" -o "${RUN_DIR}/evidence/scrna_here.html" > "${RUN_DIR}/evidence/scrna_here.log" 2>&1`. Passes (IMG-RUN, IMG-GATHER): exit 0; the log has `kernel has scanpy: False`, `AnnData v1 normalized 59 500 …` and `AnnData v2 normalized 200 500 …` with paths under `${RUN_DIR}/store`; `grep -c 'importing to docker'` on the log is 1 on a fresh build, 0 when docker already holds the image.
3. IMG-STORE: list the index's records, then read each file in the scrna image.

   ```bash
   pixi run python - <<'EOF' 2>&1 | grep -v INFO > "${RUN_DIR}/evidence/assembled.tsv"
   import asyncio
   from stargazer.assets.asset import assemble
   async def main():
       for a in sorted(await assemble(asset="anndata", stage="normalized"), key=lambda a: a.sample_id):
           print(a.sample_id, a.n_obs, a.n_vars, a.cid, await a.fetch(), sep="\t")
   asyncio.run(main())
   EOF
   cat > "${RUN_DIR}/check.py" <<'EOF'
   import sys
   import numpy as np, scanpy as sc, scipy.sparse as sp
   dense = lambda m: m.toarray() if sp.issparse(m) else np.asarray(m)
   inputs = {"v1": sys.argv[1], "v2": sys.argv[2]}
   for line in open(sys.argv[3]):
       sample, n_obs, n_vars, cid, path = line.rstrip("\n").split("\t")
       out, raw = sc.read_h5ad(path), sc.read_h5ad(inputs[sample])
       counts = dense(out.layers["counts"])
       expect = sc.AnnData(counts.copy()); sc.pp.normalize_total(expect); sc.pp.log1p(expect)
       print(sample, "shape", out.shape == (int(n_obs), int(n_vars)),
             "counts==input", np.array_equal(counts, dense(raw.X)),
             "X==log1p(normalize_total)", np.allclose(dense(out.X), dense(expect.X)))
   EOF
   F="$PWD/tests/fixtures/scrna"; IMG=$(pixi run python -c "from stargazer.tasks.scrna.env import scrna_env; print(scrna_env.image.uri)" 2>/dev/null | tail -1)
   docker run --rm --platform linux/amd64 -v "${RUN_DIR}:${RUN_DIR}:ro" -v "${F}:${F}:ro" "$IMG" \
     python "${RUN_DIR}/check.py" "$F/qc_filtered.h5ad" "$F/synthetic_200x500.h5ad" "${RUN_DIR}/evidence/assembled.tsv"
   ```

   Passes: two rows (v1 59×500, v2 200×500), and each check line reads `shape True counts==input True X==log1p(normalize_total) True`.
4. IMG-FAIL: call `local_image.run_in_image(normalize, {"adata": AnnData(path=<p>, sample_id="bad")})` for `p` a missing file and for a text file named `.h5ad`. Passes: `RuntimeError` starting `scrna.normalize failed in stargazer-scrna:<hash> (exit 1):`, holding `FileNotFoundError: … doesn't exist and has no CID` and `OSError: Unable to synchronously open file (file signature not found)` respectively; no `image-run-*` left in `$STARGAZER_LOCAL`.

### Gotchas

- Two samples with byte-identical outputs share a CID, and the index keeps one record per CID, so dispatching the same input twice under two sample IDs leaves one record. Use distinct inputs.
- A source change rebuilds the image (its tag hashes the checkout), about 70 s on osx-arm64 with the base layers cached. A run with the image already built took 18 s for both samples, emulated.
- A missing input directory isn't mounted, so the task's own error reports it; mounting it would make docker refuse with `mounts denied`.

Came out of [[pixi-development]], where it was deferred.

## Outcome

PR 134 shipped the docker path: "On this machine" runs a package task in its own task image under docker, so a notebook's header needs no domain packages where docker runs (the `local_image` module, merged in 45c099e). Verified with a notebook whose kernel had no scanpy normalizing two samples in the scrna image, the stored outputs read back and checked in that image, and the tasks tier (recipe and evidence above). Ticket `run-modes` carries it forward: "On this machine" installs the task's own header with pixi, with docker kept for a host the header can't solve on, and covers what's left here (hosted pods, notebook tasks, workflows spanning domains).

Related: [[board]], [[run-modes]], [[pixi-development]], [[pixi-notebook-sandbox]], [[local-remote-toggle]], [[flyte-images]].
