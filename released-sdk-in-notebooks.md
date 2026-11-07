---
title: released-sdk-in-notebooks
status: doing
priority: normal
created: 2026-11-04
---

The notebook headers install the SDK editable from the image's `/stargazer`, so a hosted kernel is a checkout: `task_image()` finds `pyproject.toml` there and builds task images from source on every cluster run, and production runs an editable install. Once [[release-task-images]] publishes a release's task images, the headers can depend on the released `stargazer-bio` at the image's own version instead. A hosted kernel would then run its tasks on the published images, building nothing, and the notebook image would need no `/stargazer` source tree for its kernels.

## Findings (2026-11-07)

- **The pin: a non-editable path source, `stargazer-bio = { path = "/stargazer" }`** (read in `runtime/Dockerfile`). The image's `/stargazer` is the tagged checkout the release builds the image from, so a header that installs it non-editable gets exactly the image's version with nothing to edit at a release, and works for any image a community notebook opens in. A PyPI pin would need editing at each release and would race the `package` job, which publishes in parallel with the image. Installed non-editable, `PROJECT_ROOT` is the environment's `lib/python3.14`, so `_checkout()` is false and `task_image()` takes the published image (inferred from `config.py`; measured in the verification below).
- **A checkout keeps the editable SDK without the header** (read in `pyproject.toml`). `/stargazer` doesn't exist in a checkout, so `marimo edit --sandbox` from one never used the header's source; development opens notebooks with `pixi run marimo edit <notebook>`, in the default environment, where the SDK is editable from the checkout and builds from source. Nothing changes there.
- **The tutorials' prebuilt environments follow the headers** (read in `runtime/Dockerfile`): the warm-cache loop runs `pixi install --script` on each built-in notebook, so it builds them non-editable with no change of its own. `/stargazer` stays: the headers build from it and the MCP server runs editable from it.
- **A tutorial's cluster run builds an image today even on the released SDK.** `tutorial_env` (and the template's `my_env`) is `core_image(...).with_pip_packages("marimo>=0.23,<0.24")`; installed, `core_image()` is a Debian base plus `stargazer-bio==<version>` from PyPI, a build in the owner's project. So the release publishes the core image too, `stargazer-core:<version>`, and an installed `core_image()` is `from_base` of it. A notebook's own task pod imports the notebook to find its task, so the core image carries marimo: a `notebook` dependency group that `dev` includes and pixi's `core` environment takes, so its pin stays in one place. The tutorial and the template drop their marimo layer. An installed `core_image()` is a plain `from_base`, which Flyte can't add layers to without a clone (a clone is a new image, built), so the template says to `.clone(name=..., extendable=True)` before adding packages.
- **Code bundle** (read in Flyte 2.12.4's `_code_bundle/_utils.py`). `init_flyte()` roots a hosted run's bundle at the directory holding the `stargazer` package, which is now site-packages, and Flyte never bundles site-packages files. The tutorials' tasks are imported from the installed package, so the pod runs them from the published image's own copy of the same version.
- **`stargazer-core` is a new GHCR package.** New org packages start internal, so the first release that pushes it needs it set public once, or Union can't pull it.

## Plan

- [ ] `core_image()`: marimo in the `core` environment via a `notebook` dependency group (relock with `cli/lock_envs.py`); installed, `from_base(released_image("stargazer-core", version))`. `cli/publish_task_images.py` publishes it beside the domains' images. The tasks tutorial and the template drop their marimo layer; the template's comment says to clone before adding packages. Unit test: an installed core image is the published one, with no layers.
- [ ] The six built-in headers install `/stargazer` non-editable. The Dockerfile's comments, `init_flyte()`'s docstring.
- [ ] Docs: getting-started's header example, runtime.md's image, configuration.md's images, release.yml's description, the wiki's `flyte-images`.
- [ ] Verified on Union (below): a hosted Execution tutorial's cluster run takes the published core image and builds nothing.

Deferred: the MCP server in the image still runs editable from `/stargazer` (pixi.lock's `mcp` environment), so a run an agent starts builds from source.

Related: [[board]], [[release-task-images]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
