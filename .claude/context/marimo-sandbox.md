---
sources:
  - "[[marimo-inlining-dependencies]]"
  - docs/architecture/runtime.md
  - runtime/Dockerfile
---

# marimo sandbox

How a marimo notebook carries its own dependencies and gets a venv of its own. Source: [[marimo-inlining-dependencies]].

- **`--sandbox`** (on `marimo edit`, `run` or `new`) records the notebook's packages in its own file and runs it in an isolated uv venv holding only those. A sandboxed notebook also runs as a script with `uv run notebook.py`. It needs uv.
- **The record is a PEP 723 header**: a `# /// script` comment block that is a pyproject inlined, with `requires-python` and `dependencies`. See [[marimo-inlining-dependencies#Inline script metadata]].
- **The editor adds imports to the header** when it sees a third-party import, and the package panel adds and removes them; removing an import leaves its package. By hand, `uv add --script` and `uv remove --script` edit it.
- **`[tool.uv.sources]`** in the header points a package somewhere other than PyPI: a local path (optionally editable), a git URL, or a named `[[tool.uv.index]]`.
- **Before syncing, the sandbox adds `marimo` to a header that lacks it** (`uv add --script`), then builds the venv with `uv sync --script --compile-bytecode` and starts the kernel under `uv run --with marimo==<launcher version>` layered over it. The server itself runs under a `--with marimo[lsp]` layer. Read in marimo 0.25.1's `_environments/`.
- **uv keys a script's venv on the script's absolute path** (`environments-v2/<name>-<hash>` in its cache), so the same header at two paths gets two venvs, and an edited header updates its venv in place.
- **uv's environment variables configure the sandbox**, such as `UV_PYTHON` for the Python version and `UV_LINK_MODE`.
- **`--sandbox=pixi`** builds a conda environment from the same header with `pixi install --script` (pixi 0.82 or later; Flyte's image builder pins 0.72.2, which lacks it). `[tool.pixi.dependencies]` adds conda packages, `[tool.pixi.workspace]` their channels, and `[tool.pixi.pypi-dependencies]` points a PyPI package at a path, where `[tool.uv.sources]` is ignored. The `marimo` layers over the server and the kernel still ride uv, through `pixi exec --spec "uv>=0.12" uv run --with ...`. `marimo export` has no pixi option. Read in marimo 0.25.1's `_environments/pixi.py`.
- **pixi keys a script's environment on its path** too (`cached-envs-v0/<name>-<hash>` in its cache). Without `python` pinned under `[tool.pixi.dependencies]` it takes conda-forge's newest Python over `requires-python`. Extras on a package in `dependencies` carry over to its `[tool.pixi.pypi-dependencies]` entry, and an editable path package isn't rebuilt when the environment is reused. Measured with pixi 0.83.0.
- **pixi's link settings** (`allow-hard-links`, `allow-ref-links`, `allow-symbolic-links`, or `PIXI_NO_HARD_LINKS` and the like) choose both how conda packages are linked and uv's link mode for PyPI ones. With symlinks disallowed, conda packages that contain symlinks fail to link.

## In Stargazer

- **Notebooks run in pixi's sandbox** (`runtime/launch-notebook.sh`), so a header declares bioconda's tools beside its Python packages.
- **Every notebook's header points `stargazer-bio` at `/stargazer`** through `[tool.pixi.pypi-dependencies]`, so a sandbox installs the SDK the image was built with. How the image sets that up is in `docs/architecture/runtime.md` and `runtime/Dockerfile`.
- **The image warms pixi's and uv's caches** with the built-in notebooks' packages and, in its `amd64` build, each domain's (the header of its `env.py`), and prebuilds each tutorial's environment at the path a hosted pod opens it from, so they open without installing. The built-in headers list `marimo` so the sandbox leaves them unedited.
