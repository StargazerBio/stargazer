---
title: pixi-notebook-sandbox
status: next
priority: normal
created: 2026-11-03
---

Notebooks build their environments with pixi instead of uv, so a notebook's header can declare conda packages (bioconda's tools) beside its PyPI ones, and the notebook image stops installing gatk4, samtools, bwa and bwa-mem2 with an unpinned `micromamba create` in `runtime/Dockerfile`. The second stage of [[pixi-dependencies]], which moved the task images to pixi.lock and holds what the docs and Flyte's code say about marimo's pixi sandbox.

- pixi in the notebook image, `--sandbox=pixi` in `runtime/launch-notebook.sh`.
- Notebook headers point at the SDK through `[tool.pixi.pypi-dependencies]` (pixi ignores `[tool.uv.sources]`).
- The warm cache redone for pixi (rattler's cache in place of `/opt/uv-cache`).
- The micromamba block in `runtime/Dockerfile` goes; the germline notebook declares its tools in its header.
- The notebook template's and the tasks tutorial's `with_uv_project` environments move to `with_pixi_project`.

Open questions, from [[pixi-dependencies]]: open times against uv for a core notebook and the germline notebook; the kernel's `--with marimo` overlay over a conda prefix; the conda-to-PyPI name mapping, which pixi fetches from the network; whether hosted pods still need a declared `main_env` image for tools.

Verify a core notebook and the germline notebook locally and hosted, timed against uv.

Related: [[board]], [[pixi-dependencies]], [[marimo-sandbox]], [[local-notebook-images]], [[warm-uv-cache]].
