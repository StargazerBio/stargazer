---
title: hosted-local-runs
status: maybe
priority: low
created: 2026-11-07
---

In a checkout with docker, a notebook's **On this machine** runs a package task in its own task image ([[local-runs-in-task-image]]), so the notebook's header needs none of its domain's packages. A hosted notebook pod has no docker (no binary, no socket, no daemon), so there it keeps running the task in the kernel, and a hosted notebook that runs a package task on this machine still lists the domain's packages in its header.

Options: keep it as is; send a package task dispatched on this machine to the cluster from a pod, which makes the two choices the same there; or hide the choice for package tasks in a pod. Decide when a hosted notebook's header first hurts for it.

Related: [[board]], [[local-runs-in-task-image]], [[local-remote-toggle]].
