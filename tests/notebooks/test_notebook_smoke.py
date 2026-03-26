"""Smoke tests for marimo notebooks.

Verifies that every notebook in src/stargazer/notebooks/ can be
imported, that all cells parse without errors, and that no cell
redefines variables from other cells. This catches syntax errors,
broken imports, missing dependencies, and marimo reactivity
violations before deployment.
"""

import importlib
import pkgutil

import pytest

import stargazer.notebooks as notebooks_pkg

# Discover all notebook modules dynamically
_notebook_modules = [
    name
    for _, name, _ in pkgutil.iter_modules(notebooks_pkg.__path__)
    if name != "__init__"
]


@pytest.mark.parametrize("notebook", _notebook_modules)
def test_notebook_imports(notebook):
    """Verify notebook module imports without errors."""
    mod = importlib.import_module(f"stargazer.notebooks.{notebook}")
    assert hasattr(mod, "app"), f"{notebook} missing marimo App object"


@pytest.mark.parametrize("notebook", _notebook_modules)
def test_notebook_no_multiply_defined(notebook):
    """Verify no cell redefines variables from other cells."""
    mod = importlib.import_module(f"stargazer.notebooks.{notebook}")
    app = mod.app
    app._maybe_initialize()
    graph = app._graph
    multiply_defined = graph.get_multiply_defined()
    assert not multiply_defined, (
        f"{notebook} has multiply-defined variables: {multiply_defined}. "
        "Prefix cell-local variables with _ to make them private."
    )
