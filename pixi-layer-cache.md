---
title: pixi-layer-cache
status: doing
priority: normal
created: 2026-11-04
---

A source change rebuilds the task images' whole pixi environment. `with_pixi_project(..., project_install_mode="install_project")` copies the project in before `pixi install`, in one layer, so editing any module throws away the 1.4 GB gatk environment (gatk4, its JVM, samtools, bwa, bwa-mem2, every PyPI dependency) and installs it again. Locally pixi's package cache keeps that to re-linking; Union's remote builder keeps no cache between builds. Under uv the micromamba tools were a layer of their own that survived source edits.

Split it: the environment from pyproject.toml and pixi.lock alone (`dependencies_only`), cached until either changes, then the source copied in and stargazer installed into that environment without dependencies. The manifest drops stargazer-bio as an editable path dependency, which `pixi install --locked` can't satisfy without the source; pixi still takes `[project.dependencies]` as the environment's PyPI dependencies.

Found while answering how the base image and the pixi layer meet, after [[pixi-dependencies]].

Related: [[board]], [[pixi-dependencies]], [[flyte-images]].
