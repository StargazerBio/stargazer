---
title: pixi-layer-cache
status: doing
priority: normal
created: 2026-11-04
---

A source change rebuilds the task images' whole pixi environment. `with_pixi_project(..., project_install_mode="install_project")` copies the project in before `pixi install`, in one layer, so editing any module throws away the 1.4 GB gatk environment (gatk4, its JVM, samtools, bwa, bwa-mem2, every PyPI dependency) and installs it again. Locally pixi's package cache keeps that to re-linking; Union's remote builder keeps no cache between builds. Under uv the micromamba tools were a layer of their own that survived source edits.

Split it: the environment from pyproject.toml and pixi.lock alone (`dependencies_only`), cached until either changes, then the source copied in and stargazer installed into that environment without dependencies. The manifest drops stargazer-bio as an editable path dependency, which `pixi install --locked` can't satisfy without the source; pixi still takes `[project.dependencies]` as the environment's PyPI dependencies.

Found while answering how the base image and the pixi layer meet, after [[pixi-dependencies]].

## Verification recipe: source changes keep the environment layer

A source-only change rebuilds only the stargazer layer of a task image; the pixi environment layer (Python, the tools, the dependencies) comes from cache, locally and on Union's remote builder. The images still run every task, with stargazer installed non-editable in site-packages.

### Sub-features

- `layer-cache-local`: a source-only rebuild of the gatk image, local docker.
- `layer-cache-union`: the same on Union's remote builder.
- `layer-tasks`: the tasks tier and the devbox germline tests pass on the split images.
- `layer-union-run`: a task runs on each Union-built image, stargazer imported from site-packages.

### How to get to it (user POV)

Change any module in `src/stargazer/` and run a task: the image builds again, quickly.

### Driving it

Preconditions: docker, the devbox (ticket `devbox-postgres-index`), `.flyte/union.yaml` linked, no `FLYTE_IMAGE_REGISTRY` exported for the Union builds.

- **Rebuild times.** Save the script below as `time_build.py`, then from the repo root: build once warm (`uv run python time_build.py local`, then `... time_build.py $PWD/.flyte/union.yaml`), append a comment to `src/stargazer/utils/__init__.py`, time both builds again, and `git checkout` the file. Compare with the same sequence on `main` (`layer-cache-local`, `layer-cache-union`).

```python
import asyncio, sys, time
import flyte
from flyte._internal.imagebuild.docker_builder import DockerImageBuilder
from stargazer.config import PROJECT_ROOT, gatk_env

start = time.monotonic()
if sys.argv[1] == "local":
    flyte.init(root_dir=PROJECT_ROOT)
    asyncio.run(DockerImageBuilder()._build_image(gatk_env.image, push=False))
else:
    flyte.init_from_config(sys.argv[1], root_dir=PROJECT_ROOT)
    flyte.build(gatk_env.image)
print(f"BUILT {gatk_env.image.uri} in {time.monotonic() - start:.0f}s")
```

- **Tasks and devbox.** `uv run --all-extras python cli/docker_task_tests.py` exits 0; `uv run --all-extras pytest -m devbox -rP tests/devbox/test_germline.py` passes both (`layer-tasks`).
- **Union run.** The probe in ticket [[pixi-dependencies]]'s recipe; `stargazer` prints from `.../site-packages/stargazer/__init__.py` (`layer-union-run`).

### Gotchas

- The local times include loading the image into docker (`sending tarball`), about 15 s of each.

Related: [[board]], [[pixi-dependencies]], [[flyte-images]].
