---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
  - src/stargazer/config.py
  - src/stargazer/notebooks/__init__.py
  - runtime/Dockerfile
  - .github/workflows/release.yml
  - devbox/setup.sh
---

# Flyte images

How a `flyte.Image` is declared and built. Examples: [[flyte-v2-docs#Container Images]], [[flyte-sdk-examples#3. Images & Dependencies]].

- **An image is declared, not built, in code.** A `flyte.Image` starts from a `from_*` base (`from_debian_base`, `from_base` for an existing image, `from_uv_script`) and takes `with_*` layers: `with_apt_packages`, `with_pip_packages`, `with_commands`, `with_env_vars`, `with_source_folder`, `with_uv_project` and more. Flyte builds it the first time a run needs it, tagged by content hash.
- **No image means Flyte's default** (`ghcr.io/flyteorg/flyte:py{python-version}-v{flyte_version}`).
- **`from_debian_base` has no CA certificates.** Add `ca-certificates` with `with_apt_packages` or TLS fails.
- **`from_base` refuses layers until cloned** with `.clone(name=..., extendable=True)`; the name prefixes the built image's tag.
- **Two builders.** `image.builder` in the Flyte config is `local` (the Docker daemon, pushing to `FLYTE_IMAGE_REGISTRY`) or `remote` (Union's ImageBuilder, Union only). See [[flyte-config]].
- **The registry is fixed when the image is defined**, not when a later init reads the config.

## In Stargazer

- **The task images** are on the environments in `config.py`; its module docstring and the comments above `scrna_env` and `gatk_env` say how they're built and why. The image table is in `docs/architecture/configuration.md`.
- **The notebook images**: `notebook_base` in `src/stargazer/notebooks/__init__.py`, built on the image `runtime/Dockerfile` makes and `.github/workflows/release.yml` publishes.
- **Devbox builds** are in `devbox/setup.sh`.

## Related

- [[flyte-task-environments]]: where an image is attached
- [[gatk]], [[tool-help]]: the tools in `gatk_env`'s image
