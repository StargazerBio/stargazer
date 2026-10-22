"""Smoke tests for marimo notebooks.

Verifies that every notebook in src/stargazer/notebooks/ can be
imported, that all cells parse without errors, and that no cell
redefines variables from other cells. This catches syntax errors,
broken imports, missing dependencies, and marimo reactivity
violations before deployment.
"""

import importlib
from pathlib import Path

import pytest

import stargazer.notebooks as notebooks_pkg

# Every notebook under the section directories, as a dotted module name. Modules
# at the package root (`ui.py`) are helpers notebooks import, not notebooks.
_NOTEBOOKS_ROOT = Path(notebooks_pkg.__path__[0])
_notebook_modules = [
    f"{notebooks_pkg.__name__}."
    + ".".join(p.relative_to(_NOTEBOOKS_ROOT).with_suffix("").parts)
    for p in _NOTEBOOKS_ROOT.glob("*/*.py")
    if p.name != "__init__.py"
]


@pytest.mark.parametrize("notebook", _notebook_modules)
def test_notebook_parses_without_redefinitions(notebook):
    """Verify the notebook imports, exposes `app`, and no cell redefines another's variables."""
    mod = importlib.import_module(notebook)
    app = mod.app
    app._maybe_initialize()
    graph = app._graph
    multiply_defined = graph.get_multiply_defined()
    assert not multiply_defined, (
        f"{notebook} has multiply-defined variables: {multiply_defined}. "
        "Prefix cell-local variables with _ to make them private."
    )
