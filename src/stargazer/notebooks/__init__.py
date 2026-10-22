"""
### Marimo notebooks for interactive Stargazer workflows.

Researchers use these notebooks to explore data, run tasks, and visualize
results in a familiar Python-native environment. The hosted launch path
goes through the dashboard's `/launch` handler, which spawns a
per-notebook AppEnvironment.

A notebook declares the environment its pod runs in as `main_env` in its
setup block: a `flyte.app.AppEnvironment` cloned from `notebook_env`, whose
image is built on `notebook_base`. The dashboard tile's name and blurb are
declared there too:

    with app.setup:
        import flyte

        from stargazer.notebooks import notebook_base, notebook_env

        main_name = "Variant QC"
        main_description = "bcftools stats on new calls."
        main_env = notebook_env.clone_with(
            name="variant-qc",
            image=notebook_base.with_apt_packages("bcftools"),
            resources=flyte.Resources(cpu=2, memory="4Gi"),
        )

At launch the dashboard serves the notebook on `main_env`'s image, resources
and env vars, under its own name, launch command and access control.

Navigation between notebooks lives on the dashboard; notebooks themselves
carry no nav chrome. The dashboard tile registry is `app/notebooks.py`.

spec: [docs/architecture/notebook.md](../architecture/notebook.md)
"""

import os

import flyte
import flyte.app

# Stands in for the deployed notebook image wherever none is set (a notebook
# opened locally). Only a hosted launch builds a declared image, and it
# supplies the real one.
_LOCAL_NOTEBOOK_IMAGE = "notebook-app:local"

# Ephemeral disk for the kernel's sandbox venv, uv cache and workspace; set
# explicitly because the sidecar's 1Gi default is too small.
NOTEBOOK_DISK = "20Gi"

# Defaults for resources a notebook's `main_env` leaves unset; the 6Gi limit
# fits the scRNA workflow notebook.
NOTEBOOK_RESOURCES = flyte.Resources(cpu=1, memory=("2Gi", "6Gi"), disk=NOTEBOOK_DISK)


def notebook_image_base(uri: str) -> flyte.Image:
    """Return the notebook image at `uri`, ready to take more layers.

    `Image.from_base` refuses layers until the image is cloned under a name
    and marked extendable; the name prefixes the built image's tag.
    """
    return flyte.Image.from_base(uri).clone(name="notebook-custom", extendable=True)


def notebook_environment(base: flyte.Image) -> flyte.app.AppEnvironment:
    """Return the environment a notebook pod runs in by default, on `base`.

    A notebook's `main_env` is a `clone_with` of it. The dashboard sets the
    rest of the pod at launch: its name, launch command, port, access and
    scaling.
    """
    return flyte.app.AppEnvironment(
        name="notebook", image=base, resources=NOTEBOOK_RESOURCES
    )


# The image a notebook pod runs on, as hosted pods and the dashboard set it.
notebook_base = notebook_image_base(
    os.environ.get("STARGAZER_NOTEBOOK_IMAGE", _LOCAL_NOTEBOOK_IMAGE)
)

# The environment a notebook pod runs in when its notebook declares none.
notebook_env = notebook_environment(notebook_base)
