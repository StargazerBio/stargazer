"""Pre-build script: inject dynamic catalog tables into docs pages.

Reads all files from docs/, replaces {{ placeholder }} tokens with
generated content, and writes results to docs/_build/. Run this before
`zensical build`.

Usage:
    uv run python docs/gen_catalog.py
    uv run zensical build
"""

import shutil
from pathlib import Path

from stargazer.registry import TaskRegistry
from stargazer.types import ASSET_REGISTRY

registry = TaskRegistry()
DOCS = Path(__file__).parent
BUILD = DOCS / "_build"


def _task_table(category: str) -> str:
    items = registry.to_catalog(category=category)
    if not items:
        return "*No entries registered.*"
    rows = [
        "| Name | Description | Parameters |",
        "|------|-------------|------------|",
    ]
    for item in items:
        params = ", ".join(f"`{p['name']}` ({p['type']})" for p in item["params"])
        rows.append(f"| `{item['name']}` | {item['description']} | {params} |")
    return "\n".join(rows)


def _asset_table() -> str:
    if not ASSET_REGISTRY:
        return "*No asset types registered.*"
    rows = [
        "| Asset Key | Class | Module | Fields |",
        "|-----------|-------|--------|--------|",
    ]
    for asset_key, cls in sorted(ASSET_REGISTRY.items()):
        module = cls.__module__.split(".")[-1]
        fields = sorted(set(cls._field_defaults) | set(cls._field_types))
        field_str = ", ".join(f"`{f}`" for f in fields) if fields else "—"
        rows.append(
            f"| `{asset_key}` | `{cls.__name__}` | `types/{module}.py` | {field_str} |"
        )
    return "\n".join(rows)


def _api_directives() -> str:
    src = DOCS.parent / "src"
    sections: dict[str, list[str]] = {}
    for path in sorted(src.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        module = ".".join(path.relative_to(src).with_suffix("").parts)
        parts = path.relative_to(src / "stargazer").parts
        section = parts[0].replace("_", " ").title() if parts else "Other"
        sections.setdefault(section, []).append(f"::: {module}")
    lines = []
    for section, directives in sections.items():
        lines += [f"## {section}", ""] + directives + [""]
    return "\n".join(lines)


REPLACEMENTS = {
    "architecture/tasks.md": {"catalog": _task_table("task")},
    "architecture/workflows.md": {"catalog": _task_table("workflow")},
    "architecture/types.md": {"catalog": _asset_table()},
    "reference/api.md": {"api": _api_directives()},
}


def build():
    if BUILD.exists():
        shutil.rmtree(BUILD)
    shutil.copytree(
        DOCS, BUILD, ignore=shutil.ignore_patterns("_build", "gen_catalog.py")
    )

    for rel_path, tokens in REPLACEMENTS.items():
        target = BUILD / rel_path
        src = target.read_text()
        for placeholder, content in tokens.items():
            src = src.replace("{{ " + placeholder + " }}", content)
        target.write_text(src)

    print(f"Generated docs -> {BUILD}")


if __name__ == "__main__":
    build()
