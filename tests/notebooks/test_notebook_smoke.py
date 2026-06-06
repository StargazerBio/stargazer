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

# Notebooks live in section directories (tutorials/, workflows/, workspace/)
# that aren't Python packages — no __init__.py. pkgutil won't descend into
# them, so walk the filesystem and rebuild dotted module names manually.
_NOTEBOOKS_ROOT = Path(notebooks_pkg.__path__[0])
_notebook_modules = [
    f"{notebooks_pkg.__name__}."
    + ".".join(p.relative_to(_NOTEBOOKS_ROOT).with_suffix("").parts)
    for p in _NOTEBOOKS_ROOT.rglob("*.py")
    if p.name != "__init__.py"
]


@pytest.mark.parametrize("notebook", _notebook_modules)
def test_notebook_imports(notebook):
    """Verify notebook module imports without errors."""
    mod = importlib.import_module(notebook)
    assert hasattr(mod, "app"), f"{notebook} missing marimo App object"


@pytest.mark.parametrize("notebook", _notebook_modules)
def test_notebook_no_multiply_defined(notebook):
    """Verify no cell redefines variables from other cells."""
    mod = importlib.import_module(notebook)
    app = mod.app
    app._maybe_initialize()
    graph = app._graph
    multiply_defined = graph.get_multiply_defined()
    assert not multiply_defined, (
        f"{notebook} has multiply-defined variables: {multiply_defined}. "
        "Prefix cell-local variables with _ to make them private."
    )
