---
title: local-notebook-images
status: maybe
priority: low
created: 2026-11-03
---

Locally, `docker run` starts the Stargazer image as it is: a notebook's `main_env` isn't used, and since the container doesn't run as root, only Python packages (from a notebook's header) and conda packages (`micromamba install`) can be added, the conda ones until it stops. Two ways to give local users more, both deferred:

- **Run a notebook's declared image locally.** `flyte build <notebook>.py main_env` loads a marimo notebook and builds its `main_env` image (measured 2026-11-03 with a copy of the blank template plus `with_apt_packages("bcftools")`), but it needs a registry to push to (`FLYTE_IMAGE_REGISTRY`; a throwaway `registry:2` worked), builds `linux/amd64` only (emulated on Apple silicon), and the image it builds runs as **root**, with `UV_PYTHON=/opt/venv/bin/python` and `UV_COMPILE_BYTECODE=1` set (Flyte's builder template ends `from_base` images on `USER root`). The setup block has to import `notebook_base` itself; the templates only import `notebook_env`. Whether a notebook then runs on it locally is unverified: a kernel never started under amd64 emulation, on the plain base image too.
- **Persist conda installs from the host.** Since ticket [[warm-uv-cache]], `micromamba install <package>` works in a notebook's terminal: the prefix is `/opt/conda`, owned by the `flyte` user and last on every process's path, with conda-forge and bioconda in `/opt/conda/.condarc` (measured: samtools 1.25 installed in 16 s and the running kernel called it). It's gone when the container stops. Mounting a host directory at `/opt/conda` would keep it, but hides the image's `.condarc` (so the channels would need setting another way, e.g. `CONDARC` or the `channels` key in `~/.mambarc`), and on Linux the mount's owner has to match the container's uid (a guess).

Related: [[board]], [[warm-uv-cache]], [[layered-notebook-image-cache]].
