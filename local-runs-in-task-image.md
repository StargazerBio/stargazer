---
title: local-runs-in-task-image
status: maybe
priority: normal
created: 2026-11-04
---

A notebook's **On this machine** runs a domain's tasks inside the kernel, so the notebook's own header has to list the domain's packages: scanpy's stack for scRNA, and gatk4, samtools and bwa-mem2 for germline. The task's environment already declares those packages in its domain's `env.py` header. Running the task in its own image, under docker, would mean no notebook ever installs a domain's packages, and the local run would be the same environment as the cluster run.

Open questions:
- Can Flyte 2 run a task in its container locally? If not, `stargazer.notebooks.ui.dispatch` does it, the way `cli/docker_task_tests.py` runs the tasks tier.
- A hosted notebook pod has no docker. There, "On this machine" may have to keep running in the kernel, or turn into a cluster run.
- On Apple silicon the amd64 images run emulated, and GenomicsDB has no arm64 build, so joint calling would be slow but correct.

Measured 2026-11-04 on osx-arm64 with pixi 0.84.1, using a copy of `tasks/scrna/env.py`'s header:
- As written, `pixi install --script` refuses, because the header lists only `linux-64`.
- With `osx-arm64` added to the header's platforms, it solves and installs in 23 s, and scanpy 1.12.5 imports. The SDK it carries is the released `stargazer-bio` from PyPI, so the checkout goes on top with `PYTHONPATH=src`.
- With pytest and pytest-asyncio added to that environment via `uv pip`, `PYTHONPATH=src python -m pytest -m tasks tests/tasks/scrna` passed 14 of 15 in 42 s. `test_sample_isolation.py::test_parallel_samples_write_distinct_files[normalize]` failed once and passed 6 of 6 when rerun alone.

So for scRNA, a native run needs `osx-arm64` in the header (and a lock for it) and a supported way to add the checkout and the test tools. Docker isn't needed. The gatk header is the hard case: GenomicsDB is x86_64 only.

Came out of [[pixi-development]], where it was deferred.

Related: [[board]], [[pixi-development]], [[pixi-notebook-sandbox]], [[local-remote-toggle]], [[flyte-images]].
