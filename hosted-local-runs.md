---
title: hosted-local-runs
status: done
priority: low
created: 2026-11-07
pr: 137
---

In a checkout with docker, a notebook's **On this machine** runs a package task in its own task image ([[local-runs-in-task-image]]), so the notebook's header needs none of its domain's packages. A hosted notebook pod has no docker (no binary, no socket, no daemon), so there it keeps running the task in the kernel, and a hosted notebook that runs a package task on this machine still lists the domain's packages in its header.

Options: keep it as is; send a package task dispatched on this machine to the cluster from a pod, which makes the two choices the same there; or hide the choice for package tasks in a pod. Decide when a hosted notebook's header first hurts for it.

Settled by ticket `run-modes` (PR 137), as the first option: "On this machine" runs in the kernel everywhere, a hosted pod included, so a notebook lists the packages and tools of what it runs there. The docker path is gone, and the notebook image's warm cache holds each domain's packages, so listing them costs a hosted notebook little at open. Measured on the tenant: the germline workflow ran "On this machine" in a pod whose notebook header lists gatk4, samtools and bwa-mem2.

## Outcome

Settled by PR 137, merged 2026-11-09, as the first option: "On this machine" runs in the kernel in a hosted pod too. Verified in ticket [[run-modes]] (KERNEL-HOSTED). No comments at merge; nothing left.

Related: [[board]], [[local-runs-in-task-image]], [[local-remote-toggle]].
