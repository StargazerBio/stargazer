---
title: local-notebook-images
status: maybe
priority: low
created: 2026-11-03
---

Locally, `docker run` starts the Stargazer image as it is: a notebook's `main_env` isn't used, and since the container doesn't run as root, only Python packages (from a notebook's header) and conda packages (`micromamba install`, kept across containers with a volume at `/opt/conda`, since ticket [[warm-uv-cache]]) can be added. Deferred:

- **Run a notebook's declared image locally.** `flyte build <notebook>.py main_env` loads a marimo notebook and builds its `main_env` image (measured 2026-11-03 with a copy of the blank template plus `with_apt_packages("bcftools")`), but it needs a registry to push to (`FLYTE_IMAGE_REGISTRY`; a throwaway `registry:2` worked), builds `linux/amd64` only (emulated on Apple silicon), and the image it builds runs as **root**, with `UV_PYTHON=/opt/venv/bin/python` and `UV_COMPILE_BYTECODE=1` set (Flyte's builder template ends `from_base` images on `USER root`). The setup block has to import `notebook_base` itself; the templates only import `notebook_env`. Whether a notebook then runs on it locally is unverified: a kernel never started under amd64 emulation, on the plain base image too.
Related: [[board]], [[warm-uv-cache]], [[layered-notebook-image-cache]].
