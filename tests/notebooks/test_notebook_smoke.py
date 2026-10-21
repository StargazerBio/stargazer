"""Smoke tests for marimo notebooks.

Verifies that every notebook — the SDK's tutorials in
src/stargazer/notebooks/, the dashboard's create seeds in app/seeds/, and the
repo's own notebooks in the top-level notebooks/ folder — can be imported,
that all cells parse without errors, and that no cell redefines variables
from other cells. This catches syntax errors, broken imports, missing
dependencies, and marimo reactivity violations before deployment.
"""

import importlib
import importlib.util
from pathlib import Path

import pytest

import app.seeds as seeds_pkg
import stargazer.notebooks as notebooks_pkg


def _package_notebooks(pkg, pattern: str) -> list[str]:
    """Dotted module names of the notebooks under a package, by glob pattern."""
    root = Path(pkg.__path__[0])
    return [
        f"{pkg.__name__}." + ".".join(p.relative_to(root).with_suffix("").parts)
        for p in sorted(root.glob(pattern))
        if p.name != "__init__.py"
    ]


# Modules at the SDK package root (`ui.py`) are helpers notebooks import, not
# notebooks, so only the section directories count there.
_REPO_NOTEBOOKS = Path(__file__).resolve().parents[2] / "notebooks"
_notebooks = [
    *_package_notebooks(notebooks_pkg, "*/*.py"),
    *_package_notebooks(seeds_pkg, "*.py"),
    *sorted(_REPO_NOTEBOOKS.glob("*.py")),
]


def _load(notebook: str | Path):
    """Import a notebook by module name, or a repo notebook by its path."""
    if isinstance(notebook, str):
        return importlib.import_module(notebook)
    spec = importlib.util.spec_from_file_location(notebook.stem, notebook)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _id(notebook: str | Path) -> str:
    """A readable test id: the module name, or the path from the repo root."""
    return notebook if isinstance(notebook, str) else f"notebooks/{notebook.name}"


@pytest.mark.parametrize("notebook", _notebooks, ids=_id)
def test_notebook_imports(notebook):
    """Verify notebook module imports without errors."""
    mod = _load(notebook)
    assert hasattr(mod, "app"), f"{notebook} missing marimo App object"


@pytest.mark.parametrize("notebook", _notebooks, ids=_id)
def test_notebook_no_multiply_defined(notebook):
    """Verify no cell redefines variables from other cells."""
    app = _load(notebook).app
    app._maybe_initialize()
    graph = app._graph
    multiply_defined = graph.get_multiply_defined()
    assert not multiply_defined, (
        f"{notebook} has multiply-defined variables: {multiply_defined}. "
        "Prefix cell-local variables with _ to make them private."
    )
