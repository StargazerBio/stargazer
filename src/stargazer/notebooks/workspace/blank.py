# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "stargazer",
# ]
#
# [tool.uv.sources]
# stargazer = { path = "/stargazer", editable = true }
# ///
"""### Blank workspace notebook.

An empty marimo notebook for authoring from scratch. `/workspace/create`
copies this seed under your chosen name and injects a `[tool.stargazer]`
resource block into the header above — edit those values to rightsize the
pod for your workload.

spec: [docs/architecture/notebook.md](../../docs/architecture/notebook.md)
"""

import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    """Imports."""
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
