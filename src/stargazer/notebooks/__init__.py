"""
### Marimo notebooks for interactive Stargazer workflows.

Researchers use these notebooks to explore data, run tasks, and visualize
results in a familiar Python-native environment. The hosted launch path
goes through the dashboard's `/launch` handler, which spawns a
per-notebook AppEnvironment whose image is built programmatically by
`app.per_notebook.notebook_app_img_recipe`.

A notebook can declare its own pod image in its setup block, as a
`main_img` built on `notebook_base`:

    with app.setup:
        from stargazer.notebooks import notebook_base

        main_img = notebook_base.with_apt_packages("bcftools")

The dashboard evaluates that expression at launch and serves the notebook on
the built image.

A notebook's setup calls `init_flyte()` rather than `flyte.init_from_config()`,
so that in a hosted pod, which has no config file, `flyte.run` reaches the
cluster instead of quietly running in-process.

Navigation between notebooks lives on the dashboard; notebooks themselves
carry no nav chrome. The dashboard tile registry is `app/notebooks.py`.

spec: [docs/architecture/notebook.md](../architecture/notebook.md)
"""

import contextlib
import os
from pathlib import Path

import flyte

# Stands in for the deployed notebook image wherever none is set (a notebook
# opened locally). Only a hosted launch builds `main_img`, and it supplies the
# real one.
_LOCAL_NOTEBOOK_IMAGE = "notebook-app:local"


def notebook_image_base(uri: str) -> flyte.Image:
    """Return the notebook image at `uri`, ready to take more layers.

    `Image.from_base` refuses layers until the image is cloned under a name
    and marked extendable; the name prefixes the built image's tag.
    """
    return flyte.Image.from_base(uri).clone(name="notebook-custom", extendable=True)


# The image a notebook pod runs on, as hosted pods and the dashboard set it.
notebook_base = notebook_image_base(
    os.environ.get("STARGAZER_NOTEBOOK_IMAGE", _LOCAL_NOTEBOOK_IMAGE)
)


def init_flyte() -> None:
    """Initialize Flyte for a notebook's kernel, wherever it runs.

    A hosted notebook pod (`_U_EP_OVERRIDE` set) has no config file, but it
    carries the endpoint, an API key and the owner's org, project and domain,
    which make an in-cluster client for the owner's project. Its runs bundle
    code from the directory holding the `stargazer` package, where the SDK and
    the image-baked notebooks' tasks live. Anywhere else the config file
    decides, as `flyte.init_from_config()` does: with none, runs stay in the
    notebook's own process.
    """
    if not os.environ.get("_U_EP_OVERRIDE"):
        flyte.init_from_config()
        return
    # `init_in_cluster` takes the code bundle's root from the cwd and has no
    # parameter for it. A pod's cwd is the workspace, which holds no SDK code.
    with contextlib.chdir(Path(__file__).resolve().parents[2]):
        flyte.init_in_cluster(
            org=os.environ.get("FLYTE_ORG"),
            project=os.environ.get("FLYTE_PROJECT"),
            domain=os.environ.get("FLYTE_DOMAIN"),
        )
