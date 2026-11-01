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
- **uv's environment variables configure the sandbox**, such as `UV_PYTHON` for the Python version and `UV_LINK_MODE`.

## In Stargazer

- **Every notebook's header points `stargazer-bio` at `/stargazer`** through `[tool.uv.sources]`, so a sandbox installs the SDK the image was built with. How the image sets that up is in `docs/architecture/runtime.md` and `runtime/Dockerfile`.
