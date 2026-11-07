---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
  - src/stargazer/config.py
  - src/stargazer/tasks/gatk/env.py
  - src/stargazer/tasks/scrna/env.py
  - src/stargazer/notebooks/__init__.py
  - runtime/Dockerfile
  - .github/workflows/release.yml
  - cli/publish_task_images.py
  - devbox/setup.sh
---

# Flyte images

How a `flyte.Image` is declared and built. Examples: [[flyte-v2-docs#Container Images]], [[flyte-sdk-examples#3. Images & Dependencies]].

- **An image is declared, not built, in code.** A `flyte.Image` starts from a `from_*` base (`from_debian_base`, `from_base` for an existing image, `from_uv_script`, `from_pixi_script`) and takes `with_*` layers: `with_apt_packages`, `with_pip_packages`, `with_commands`, `with_env_vars`, `with_source_folder`, `with_uv_project`, `with_pixi_project` (a pixi environment, conda and PyPI packages, which becomes the image's Python) and more. Flyte builds it the first time a run needs it, tagged by content hash.
- **`from_pixi_script` builds from a PEP 723 header**, `[tool.pixi.*]` tables included: Flyte renders the header as a `pixi.toml` workspace and installs it with `pixi install`, `--locked` when `<script>.pixi.lock` sits beside it. The header and its lock feed the image hash and the script's code doesn't, so editing the code reuses the image. Its debian base has no Flyte venv (`/opt/venv`); the pixi environment is the image's Python, so `flyte` must be among its packages. Union's builder lowers it to primitive layers, as it does `with_pixi_project`.
- **Flyte's builder pins its pixi** (`PIXI_VERSION` in `flyte/_internal/imagebuild/utils.py`, 0.72.2 for Flyte 2.12.4), which has no `--script` commands and reads a lock from a newer pixi (0.8x) as out of date: the platform's virtual packages are written differently. A lock the build accepts is one that pixi wrote.
- **No image means Flyte's default** (`ghcr.io/flyteorg/flyte:py{python-version}-v{flyte_version}`).
- **`from_debian_base` has no CA certificates.** Add `ca-certificates` with `with_apt_packages` or TLS fails.
- **`from_base` refuses layers until cloned** with `.clone(name=..., extendable=True)`; the name prefixes the built image's tag.
- **Two builders.** `image.builder` in the Flyte config is `local` (the Docker daemon, pushing to `FLYTE_IMAGE_REGISTRY`) or `remote` (Union's ImageBuilder, Union only). See [[flyte-config]].
- **The registry is fixed when the image is defined**, not when a later init reads the config.
- **`with_source_folder` filters by a `.dockerignore`**: a `with_dockerignore` layer's, else the one at `flyte.init`'s `root_dir` (`get_and_list_dockerignore` in `flyte/_internal/imagebuild/utils.py`). Without one the folder ships whole, and everything in it feeds the image hash and the build context.

## In Stargazer

- **The task images** are on the environments in each domain's `env.py`, built by `task_image()` in `config.py`; images for tasks that need only the SDK by `core_image()`, from `pyproject.toml`'s `core` environment. Their docstrings say how and why; `cli/lock_envs.py` locks the headers and `pixi.lock` with the builder's pixi. A checkout builds them; an installed package takes `from_base` of the ones its release published (`released_image()`), which `cli/publish_task_images.py` builds, the core image too, as `stargazer-core`, and version-tags in `.github/workflows/release.yml`; the notebooks' headers install the image's `/stargazer` non-editable, so a notebook's kernel is an installed package and takes the published images. The image table is in `docs/architecture/configuration.md`.
- **The notebook images**: `notebook_base` in `src/stargazer/notebooks/__init__.py`, built on the image `runtime/Dockerfile` makes and `.github/workflows/release.yml` publishes.
- **Devbox builds** are in `devbox/setup.sh`.

## Related

- [[flyte-task-environments]]: where an image is attached
- [[gatk]], [[tool-help]]: the tools in `gatk_env`'s image
