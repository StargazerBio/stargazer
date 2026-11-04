---
title: release-task-images
status: review
priority: normal
created: 2026-11-04
pr: 132
---

A release publishes the task images, and an installed `stargazer-bio` runs its tasks on them instead of building from source. Today `gatk_env` and `scrna_env` build from `PROJECT_ROOT / "pyproject.toml"`, which exists only in a checkout or the notebook image's `/stargazer`. Installed from PyPI, `PROJECT_ROOT` is `<venv>/lib/python3.14` and the build fails (measured 2026-11-04 with the wheel in a clean venv: `FileNotFoundError: Pixi manifest file .../lib/python3.14/pyproject.toml does not exist`), so SDK authoring from an IDE can't run a task remotely.

One recipe, two sources for the image:

- **Release:** `.github/workflows/release.yml`, which already pushes the notebook image to GHCR, builds both task images from the tagged checkout with the same `_task_image` recipe and pushes them under the release's version.
- **Installed package:** with no `pyproject.toml` beside it, `gatk_env` and `scrna_env` use the published image of the installed version, so nothing builds on first run.
- **Checkout:** builds from source as now, non-editable, the environment layer cached apart from the source.

With releases on prebuilt images, the notebook headers can install the released package instead of `/stargazer` editable, so production has no editable installs (ticket [[released-sdk-in-notebooks]]).

## Findings (2026-11-04)

- **Union pulls a public GHCR image for a task, with no build** (measured). A task on `flyte.Image.from_base("ghcr.io/stargazerbio/debug:release-task-images-probe")` (Flyte's own `py3.14-v2.12.4` base, retagged) ran in `u-pryce` as the org admin: run `u47xc4hbt9hktxd5s297` succeeded in 87 s, output `x86_64 py3.14.10 flyte 2.12.4`. Flyte submitted the URI as is (`from_base` with no layers builds nothing).
- **Package names: `ghcr.io/stargazerbio/stargazer-gatk` and `ghcr.io/stargazerbio/stargazer-scrna` already exist and are public** (measured with `gh api /orgs/StargazerBio/packages?package_type=container`), holding Flyte-built images from 2026-05-06 under hash tags and `latest`. They're the names Flyte gives `name="stargazer-gatk"`/`"stargazer-scrna"` with registry `ghcr.io/stargazerbio`, so a release pushes there and needs no manual visibility flip.
- **Tags: the installed version, normalized, not the git tag** (measured). `importlib.metadata.version("stargazer-bio")` returns the wheel's metadata version, which setuptools normalizes: a project at `version = "2026.11.04"` builds `…-2026.11.4-py3-none-any.whl`, while the release's git tag is `v2026.11.04`. A task image is tagged with the normalized version (`stargazer-gatk:2026.11.4`), which `release.yml` computes with `packaging.version.Version`; the notebook image keeps the git tag. Flyte tags what it builds with a content hash and has no tag parameter (`Image._final_tag` in Flyte 2.12.4), so the release builds with `flyte.build` and adds the version tag with `docker buildx imagetools create`.
- **Detecting an installed package: no `pyproject.toml` at `PROJECT_ROOT`** (measured). With PyPI's `stargazer-bio==2026.10.30` in a clean venv, `PROJECT_ROOT` is `<venv>/lib/python3.14` and `PROJECT_ROOT / "pyproject.toml"` doesn't exist; in a checkout it does. That's the check: a checkout builds from source, anything else takes `from_base("ghcr.io/stargazerbio/stargazer-<env>:<version>")`. A hosted notebook's kernel installs the SDK editable from `/stargazer`, where `pyproject.toml` sits, so it keeps building from source until [[released-sdk-in-notebooks]] moves the headers to the released package.
- **The release image is the checkout recipe, built in CI from the tagged checkout.** With [[pixi-development]]'s headers listing `stargazer-bio` unpinned, an image of the header alone would hold whatever version the header's lock picked from PyPI, and the `package` job publishes the new version in parallel. The source layer on top installs the tagged checkout, so the image holds the release's code whatever the lock says.
- **`main_env` doesn't layer on a task image** (read in `stargazer.notebooks`). It's `notebook_env.clone_with(image=notebook_base.with_*(...))`, and `notebook_base` is `from_base(STARGAZER_NOTEBOOK_IMAGE)`, the published notebook image the dashboard sets, which Union's remote builder already layers on. What does build from source in a notebook is the template's `my_env` and the tasks tutorial's environment (`with_uv_project(PROJECT_ROOT / "pyproject.toml")`): once [[released-sdk-in-notebooks]] installs the released package they find no `pyproject.toml`, and should layer on the published task image instead (`gatk_env.image.clone(name=..., extendable=True).with_*`), the same remote-builder-on-GHCR-base path `main_env` takes (inferred).

## Plan

- [x] Settle the open questions above.
- [x] `release.yml` builds `stargazer-gatk` and `stargazer-scrna` from the tagged checkout with the environment modules' recipe, pushes them to GHCR and tags them with the normalized version.
- [x] An installed package's environments use `from_base` of the published image of their version; a checkout builds from source.
- [x] Verified: a wheel in a clean venv submits a task that runs on Union on a published image (`ghcr.io/stargazerbio/debug` tags, no real release).
- [x] Docs: Configuration → Container Images, the release's description in `release.yml`, the wiki's `flyte-images`.

## Verification recipe

Without a release: copy the branch, point `released_image()` in `config.py` at `ghcr.io/stargazerbio/debug:{name}-{release}`, then in the copy `docker login ghcr.io` (with `gh auth token`) and `pixi run python cli/publish_task_images.py`, which pushes `debug:stargazer-<domain>-<version>`. Build the copy's wheel (`pixi exec --spec python-build --spec "python=3.14.*" -- pyproject-build --wheel`), install it in a clean venv, and from an empty directory submit a task on `gatk_env` and one on `scrna_env` to `u-pryce` with `.flyte/union.yaml`. Expect Flyte to build nothing ("Built image" names the GHCR URI as is), stargazer imported from `/opt/pixi-project/.pixi/envs/default`, and the tools or scanpy there. After a real release, the same script runs without the copy and with no patch. Measured 2026-11-04: runs `u7qnxnmz2clsxlldxzww` (gatk, `samtools_faidx`) and `uxftkndlrk844hfdnvr5` (scrna) succeeded.

Related: [[board]], [[pixi-layer-cache]], [[pixi-notebook-sandbox]], [[released-sdk-in-notebooks]], [[pixi-dependencies]], [[flyte-images]].
