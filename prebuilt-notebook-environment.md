---
title: prebuilt-notebook-environment
status: backlog
priority: normal
created: 2026-11-09
---

A hosted notebook installs its header's environment when it opens, in the pod, before its kernel starts. Since ticket [[run-modes]] a header lists what the notebook runs on this machine, so headers with gatk4 or scanpy are the normal case. The notebook image's warm cache holds the domains' packages, which took a header listing both from 31 s and 45 packages fetched to 8 s and 3 fetched (measured, emulated amd64), but anything else a header adds comes from the network at every cold open.

Build the environment before launch instead: the dashboard's launch builds an image layer over the Stargazer image that installs the notebook's header at the path the pod opens it from, the way `runtime/Dockerfile`'s warm-cache step does for the tutorials, keyed on the header so an unchanged notebook reuses its image. The pod then opens with the environment in place. This is infra's side (the launch) with the pod's contract in `docs/architecture/runtime.md`.

To settle first:

- Whether a layer Union's builder adds over the Stargazer image keeps the image's caches usable: ticket [[layered-notebook-image-cache]].
- What a first launch costs against today's open, and whether the wait belongs at launch or at open. A hosted open on the warm cache hasn't been timed on a pod yet.
- A header edited in the editor: the kernel's environment is rebuilt in the pod as today, and the next launch builds a new layer.

Related: [[board]], [[run-modes]], [[layered-notebook-image-cache]], [[warm-uv-cache]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
