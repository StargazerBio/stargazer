"""Every built-in notebook's PEP 723 header lists the packages it imports.

A sandboxed `marimo edit` writes an installed import the header doesn't list
into it as `name==<installed version>`, a pin a saved copy keeps after the
image moves on.
"""

import ast
import importlib.metadata
import re
import sys
import tomllib
from pathlib import Path

import pytest

import stargazer.notebooks as notebooks_pkg

_NOTEBOOKS_ROOT = Path(notebooks_pkg.__path__[0])
_NOTEBOOK_PATHS = sorted(
    p for p in _NOTEBOOKS_ROOT.glob("*/*.py") if p.name != "__init__.py"
)


def _normalize(name: str) -> str:
    """Normalize a package name to its PEP 503 form."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared(path: Path) -> set[str]:
    """Return the normalized names in the notebook header's `dependencies`."""
    lines = path.read_text().splitlines()
    start = lines.index("# /// script") + 1
    end = lines.index("# ///", start)
    body = ["" if line == "#" else line.removeprefix("# ") for line in lines[start:end]]
    header = tomllib.loads("\n".join(body))
    return {
        _normalize(re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", dep).group(0))
        for dep in header["dependencies"]
    }


def _imported_modules(path: Path) -> set[str]:
    """Return the top-level module names the notebook imports."""
    tree = ast.parse(path.read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize(
    "path",
    _NOTEBOOK_PATHS,
    ids=[str(p.relative_to(_NOTEBOOKS_ROOT)) for p in _NOTEBOOK_PATHS],
)
def test_notebook_header_declares_its_imports(path):
    """Verify every installed third-party import is declared in the header."""
    rel = path.relative_to(_NOTEBOOKS_ROOT)
    dists = importlib.metadata.packages_distributions()
    declared = _declared(path)
    missing = set()
    for module in sorted(_imported_modules(path)):
        if module in sys.stdlib_module_names or module not in dists:
            continue
        names = [_normalize(dist) for dist in dists[module]]
        if not declared.intersection(names):
            missing.add(names[0])
    assert not missing, (
        f"{rel} imports {sorted(missing)} without listing them in its header's dependencies"
    )
