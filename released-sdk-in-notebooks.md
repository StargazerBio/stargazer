---
title: released-sdk-in-notebooks
status: backlog
priority: normal
created: 2026-11-04
---

The notebook headers install the SDK editable from the image's `/stargazer`, so a hosted kernel is a checkout: `task_image()` finds `pyproject.toml` there and builds task images from source on every cluster run, and production runs an editable install. Once [[release-task-images]] publishes a release's task images, the headers can depend on the released `stargazer-bio` at the image's own version instead. A hosted kernel would then run its tasks on the published images, building nothing, and the notebook image would need no `/stargazer` source tree for its kernels.

Open questions:
- How a header pins the release the image carries without editing every notebook at each release. Options are a constraint the launch script passes to pixi, or the image's prebuilt environments.
- What a notebook author in a checkout gets: `marimo edit` from a checkout should keep the editable SDK, so local development still builds from source.
- The tutorials' prebuilt environments in the image ([[pixi-notebook-sandbox]]) are built from those headers, so they change with them.

Related: [[board]], [[release-task-images]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
