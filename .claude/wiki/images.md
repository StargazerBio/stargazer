---
sources:
  - src/stargazer/config.py
  - src/stargazer/notebooks/__init__.py
  - runtime/Dockerfile
  - .dockerignore
  - .github/workflows/release.yml
  - docs/architecture/configuration.md
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
---

# Images

Every container image Stargazer runs on, and how Flyte builds them. The table of images and where each runs is in `docs/architecture/configuration.md` (Container Images); this page holds the mechanics.

## How Flyte builds an image

- **An image is declared, not built, in code.** A `flyte.Image` starts from a `from_*` base (`from_debian_base`, `from_base` for an existing image, `from_uv_script`) and takes `with_*` layers: `with_apt_packages`, `with_pip_packages`, `with_commands`, `with_env_vars`, `with_source_folder`, `with_uv_project` and more. Flyte builds it the first time a run needs it, tagged by content hash. Examples: [[flyte-v2-docs#Container Images]], [[flyte-sdk-examples#3. Images & Dependencies]].
- **No image means Flyte's default** (`ghcr.io/flyteorg/flyte:py{python-version}-v{flyte_version}`).
- **`from_debian_base` has no CA certificates.** Add `ca-certificates` with `with_apt_packages` or TLS fails; both Stargazer task images do.
- **`from_base` refuses layers until cloned.** It needs `.clone(name=..., extendable=True)` first; `notebook_image_base()` does this, and the name prefixes the built image's tag.
- **Two builders.** `image.builder` in the Flyte config is `local` (the Docker daemon, pushing to `FLYTE_IMAGE_REGISTRY`) or `remote` (Union's ImageBuilder, Union only). See [[flyte-config]].

## Stargazer's quirks

- **The registry is fixed when the image is defined**, as `config.py` imports: from `FLYTE_IMAGE_REGISTRY` or `image.registry` in `./.flyte/config.yaml`, not from the config a later init reads. A registry in that file therefore leaks into any Union run from the same checkout, so the devbox exports `FLYTE_IMAGE_REGISTRY` instead.
- **Task images are x86_64 only** (`IMAGE_PLATFORM`), the architecture Union runs: GATK's GenomicsDB ships an x86_64-only native library, so an arm64 build can't joint-call. On an Apple-silicon devbox the cluster runs natively and these pods run emulated.
- **Devbox builds push plain images.** An arm64 node won't pull an image index with no arm64 entry, so devbox builds set `FLYTE_DOCKER_BUILD_EXTRA_ARGS=--provenance=false`.
- **The package is in the task images**, through `with_uv_project(..., project_install_mode="install_project")` with `--no-dev`, so a workflow's child tasks import as installed modules. A source change therefore builds new images; `.dockerignore` keeps docs, tests and local caches out of the build context so they don't.

## The task images

Each `TaskEnvironment` in `config.py` carries its image (see [[flyte-task-environments]]).

- **`stargazer-scrna`** (`scrna_env`): the Flyte debian base with the project's `bio` extra.
- **`stargazer-gatk`** (`gatk_env`): the debian base with micromamba layered on, and `gatk4`, `samtools`, `bwa` and `bwa-mem2` from bioconda in `/opt/conda`, each symlinked onto `PATH`. `java` is linked too, since gatk's wrapper calls the conda JVM by name. See [[gatk]] and [[tool-help]].
- **A tool a new task wraps** is layered onto its environment's image (`with_apt_packages`, `with_commands`, or the bioconda line).

## The notebook image

- **One image runs every notebook**, built from `runtime/Dockerfile`. `release.yml` builds it for amd64 and arm64 on a calendar tag and pushes `ghcr.io/stargazerbio/stargazer:<tag>` and `:latest`. Union's nodes pull it from GHCR, which is public. Joint calling works only in the amd64 variant.
- **A notebook's declared image is built on top of it.** `notebook_base` is the image named by `STARGAZER_NOTEBOOK_IMAGE` (the pod's own), and a notebook's `main_env` adds layers to it. Union's remote builder builds that image in the owner's project at launch. See [[notebooks#main_env]].

## Related

- [[runtime]]: what runs in the notebook image
- [[flyte-config]]: where `image.builder` and the registry come from
