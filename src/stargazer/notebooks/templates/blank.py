# /// script
# requires-python = ">=3.14"
# dependencies = [
#   "stargazer",
# ]
#
# [tool.uv.sources]
# stargazer = { path = "/stargazer", editable = true }
# ///
"""### Blank workspace notebook.

An empty marimo notebook for authoring from scratch. `/workspace/create`
copies this seed under your chosen name, which it sets as `main_name` in the
setup block. Edit `main_resources` there to rightsize the pod for your
workload.

spec: [docs/architecture/notebook.md](../architecture/notebook.md)
"""

import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")

with app.setup:
    import flyte

    main_description = ""
    main_resources = flyte.Resources(cpu=2, memory="4Gi")


@app.cell
def _():
    """Imports."""
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
