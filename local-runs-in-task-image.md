---
title: local-runs-in-task-image
status: doing
priority: normal
created: 2026-11-04
---

A notebook's **On this machine** runs a domain's tasks inside the kernel, so the notebook's own header has to list the domain's packages: scanpy's stack for scRNA, and gatk4, samtools and bwa-mem2 for germline. The task's environment already declares those packages in its domain's `env.py` header. Running the task in its own image, under docker, would mean no notebook ever installs a domain's packages, and the local run would be the same environment as the cluster run.

## Answers

- **Flyte 2 can't run a task in its container locally.** Measured on `flyte` 2.12.4: `Mode` in `flyte/_run.py` is `local`, `remote` or `hybrid`, and the local controller (`flyte/_internal/controllers/_local_controller.py`) runs every task through `direct_dispatch`, in the calling process. `with_runcontext(mode="local").run(normalize, ...)` from the dev environment fails with `ModuleNotFoundError: No module named 'scanpy'`. The pod entrypoint (`flyte/_bin/runtime.py`'s `a0`) can't stand in either: it calls `init_in_cluster` and makes a remote controller. So `dispatch` runs the container itself, the way `cli/docker_task_tests.py` runs the tasks tier.
- **The container is the task's own image, running the task in Flyte's local mode.** Prototyped by hand 2026-11-07 on osx-arm64, docker 29.8.2: the checkout's `stargazer-scrna` built in 69 s (cached base layers); `normalize` on `qc_filtered.h5ad`, its input pickled into a directory both sides see, ran in `docker run --platform linux/amd64 --user <uid>:<gid> -e HOME=/tmp`, with `STARGAZER_LOCAL`, `STARGAZER_STORE_ROOT` and the SQLite index's directory bind-mounted at their host paths. 18.4 s wall, emulated. The pickled output came back as a real `AnnData` with its cid, its file in the host's store and its row in the host's index, owned by the host user.
- **A hosted pod has no docker.** Measured: the notebook image (`ghcr.io/stargazerbio/debug:notebook-dockerignore`) has no `docker` binary and no `/var/run/docker.sock`, and a pod gets no daemon. There, "On this machine" keeps running in the kernel, as it does today, so a hosted notebook that runs a package task on this machine still needs its domain's packages in its header. Whether a pod should instead send package tasks to the cluster is its own decision: ticket `hosted-local-runs`.
- **Apple silicon** runs the amd64 images emulated, as the prototype did. GenomicsDB's joint calling isn't measured here.

## Plan

One case first: `marimo edit` from a checkout, docker on the PATH, dispatching a package task (one whose module is in `stargazer.tasks` or `stargazer.workflows`) on this machine.

- [ ] `stargazer.notebooks.local_image`: `runs_in_image(task)` (docker on the PATH, a package task, a `flyte.Image`); `build_image(image)`, moved from `cli/docker_task_tests.py`, which imports it; `run_in_image(task, inputs)`, which pickles the inputs into a call directory under `STARGAZER_LOCAL`, runs `python -m stargazer.notebooks.local_image` in the task's image with the store, the index's directory, `STARGAZER_LOCAL` and each input asset's directory (read-only) mounted at their host paths, the storage and Pinata variables passed through, and returns the unpickled output; a failed run raises with the container's output. Its container side imports the task by module and name and runs it with Flyte's local mode.
- [ ] `dispatch`'s local branch calls `run_in_image` when `runs_in_image(task)`, else runs in-process as before.
- [ ] Unit tests in `tests/notebooks/`: the routing (package task with docker → image; no docker, or a notebook's task → in-process) and the mounts.
- [ ] Docs: `docs/architecture/notebook.md` (Execution Context, Boundary rules), `ui.py`'s docstring, and the [[flyte]] wiki page's Running tasks (no local container mode).
- [ ] Verified in a notebook whose header has no scanpy, dispatching scRNA's `normalize` on this machine.

Later, each its own change:
- [ ] A hosted pod's "On this machine" for package tasks (ticket `hosted-local-runs`).
- [ ] A notebook's own `@app.function` tasks in their image, which needs the notebook mounted as their code.
- [ ] An installed package pulling its release's images (`released_image()`) rather than building.
- [ ] The germline workflow on Apple silicon: emulated GenomicsDB, timed.

Measured 2026-11-04 on osx-arm64 with pixi 0.84.1, using a copy of `tasks/scrna/env.py`'s header:
- As written, `pixi install --script` refuses, because the header lists only `linux-64`.
- With `osx-arm64` added to the header's platforms, it solves and installs in 23 s, and scanpy 1.12.5 imports. The SDK it carries is the released `stargazer-bio` from PyPI, so the checkout goes on top with `PYTHONPATH=src`.
- With pytest and pytest-asyncio added to that environment via `uv pip`, `PYTHONPATH=src python -m pytest -m tasks tests/tasks/scrna` passed 14 of 15 in 42 s. `test_sample_isolation.py::test_parallel_samples_write_distinct_files[normalize]` failed once and passed 6 of 6 when rerun alone.

So for scRNA, a native run needs `osx-arm64` in the header (and a lock for it) and a supported way to add the checkout and the test tools. Docker isn't needed. The gatk header is the hard case: GenomicsDB is x86_64 only.

Came out of [[pixi-development]], where it was deferred.

Related: [[board]], [[pixi-development]], [[pixi-notebook-sandbox]], [[local-remote-toggle]], [[flyte-images]].
