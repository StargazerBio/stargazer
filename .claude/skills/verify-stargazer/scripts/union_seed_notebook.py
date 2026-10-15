"""Seed a notebook that declares `main_img` into the Union test account's workspace.

Writes `main-img-probe.py`, declaring one apt package, from a task pod, which
can write the workspace store's bucket where a deployer's own AWS access may
not. The task module imports nothing but `flyte`, since the pod loads it from
a bare Flyte image.
Run from the checkout root (it reads `.flyte/union.yaml`):

    union_seed_notebook.py <apt-package>
"""

import sys
from pathlib import Path

import flyte
import flyte.storage

PROJECT, DOMAIN = "u-pryce", "development"
KEY = (
    "s3://union-us-west-2-stargazerbio/stargazer/users/387300641116005877"
    "/notebooks/main-img-probe.py"
)

NOTEBOOK = """# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "stargazer",
# ]
#
# [tool.uv.sources]
# stargazer = {{ path = "/stargazer", editable = true }}
#
# [tool.stargazer]
# name = "main_img probe"
# cpu = 1
# memory = "2Gi"
# description = "Declares its own pod image."
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")

with app.setup:
    import subprocess

    import marimo as mo

    from stargazer.notebooks import notebook_base

    main_img = notebook_base.with_apt_packages("{pkg}")


@app.cell
def _():
    probe = subprocess.run(
        ["sh", "-c", "command -v {pkg} && {pkg} --version 2>&1 | head -1"],
        capture_output=True,
        text=True,
    )
    mo.md(
        f"PROBE-TOOL: `{{probe.stdout.strip()}}` "
        f"PROBE-BASE: `{{notebook_base.base_image}}` "
        f"PROBE-MAIN: `{{type(main_img).__name__}}`"
    )
    return


if __name__ == "__main__":
    app.run()
"""

env = flyte.TaskEnvironment(
    name="nb_image_seed",
    image=flyte.Image.from_debian_base(),
    resources=flyte.Resources(cpu=1, memory="512Mi"),
)


@env.task
async def seed(content: str, key: str) -> str:
    """Write `content` to `key` in the workspace store."""

    await flyte.storage.put_stream(content.encode(), to_path=key)
    return key


if __name__ == "__main__":
    flyte.init_from_config(
        str(Path(".flyte/union.yaml").resolve()),
        project=PROJECT,
        domain=DOMAIN,
        root_dir=Path(__file__).parent,
    )
    r = flyte.run(seed, content=NOTEBOOK.format(pkg=sys.argv[1]), key=KEY)
    print("run:", r.name, r.url, flush=True)
    r.wait(quiet=True)
    print("phase:", r.phase)
    print("outputs:", r.outputs())
