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

Came out of [[pixi-development]], where it was deferred.

Related: [[board]], [[pixi-development]], [[pixi-notebook-sandbox]], [[local-remote-toggle]], [[flyte-images]].
