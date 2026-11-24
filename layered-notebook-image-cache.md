---
title: layered-notebook-image-cache
status: done
priority: normal
created: 2026-11-03
---

A notebook whose `main_env` adds layers (`notebook_base.with_apt_packages(...)`) runs on an image Union's builder builds `FROM` the Stargazer image, so it inherits the warm uv cache from ticket [[warm-uv-cache]]. Whether it keeps the speedup is untested. Flyte's builder template (the local one, `flyte/_internal/imagebuild/docker_builder.py`; Union's remote builder's is not visible) switches to `USER root` without switching back for `from_base` images, and sets `UV_PYTHON=/opt/venv/bin/python`, `UV_LINK_MODE=copy` and `UV_COMPILE_BYTECODE=1`. Replaying marimo's sync with those variables on the arm64 image, the Assets tutorial took 9 to 11 s offline instead of about 1.8 s (measured 2026-11-03); the cause isn't established.

Check it on Union: launch a workspace notebook whose `main_env` adds a layer, open it as the test account, and read the pod log's sync lines against an unlayered pod's. If the venv is rebuilt, find which variable does it and whether the base image can make it a no-op.

## Outcome

Closed unmeasured, on the user's call (2026-11-24): a layer Union's builder adds over the Stargazer image is assumed to keep the warm cache. The local replay (9 to 11 s offline instead of about 1.8 s) was never explained or checked on Union. If a layered notebook's pod log shows its environment rebuilt, reopen this.

Related: [[board]], [[warm-uv-cache]], [[local-notebook-images]].
