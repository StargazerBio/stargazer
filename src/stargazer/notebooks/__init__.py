"""
### Marimo notebooks for interactive Stargazer workflows.

Researchers use these notebooks to explore data, run tasks, and visualize
results in a familiar Python-native environment. The hosted launch path
goes through the dashboard's `/launch` handler, which spawns a
per-notebook AppEnvironment whose image is built programmatically by
`app.per_notebook.notebook_app_img_recipe`.

A notebook declares its own pod in its setup block: `main_resources`, and
`main_img` built on `notebook_base`. The dashboard tile's name and blurb are
declared there too:

    with app.setup:
        import flyte

        from stargazer.notebooks import notebook_base

        main_name = "Variant QC"
        main_description = "bcftools stats on new calls."
        main_resources = flyte.Resources(cpu=2, memory="4Gi")
        main_img = notebook_base.with_apt_packages("bcftools")

At launch the dashboard sizes the pod from `main_resources` and serves the
notebook on the built image.

Navigation between notebooks lives on the dashboard; notebooks themselves
carry no nav chrome. The dashboard tile registry is `app/notebooks.py`.

spec: [docs/architecture/notebook.md](../architecture/notebook.md)
"""

import os

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
