"""Inject dynamic content into static docs pages at build time.

Each target page contains a placeholder ({{ catalog }} or {{ api }}) that
gets replaced with content generated from the live registries.
"""

from pathlib import Path

import mkdocs_gen_files

from stargazer.registry import TaskRegistry
from stargazer.types import ASSET_REGISTRY

registry = TaskRegistry()
DOCS = Path(__file__).parent


SRC = Path(__file__).parent.parent / "src"


def _inject(page: str, **replacements: str) -> None:
    src = (DOCS / page).read_text()
    for placeholder, content in replacements.items():
        src = src.replace("{{ " + placeholder + " }}", content)
    with mkdocs_gen_files.open(page, "w") as f:
        f.write(src)
    mkdocs_gen_files.set_edit_path(page, page)


def _api_directives() -> str:
    sections: dict[str, list[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        module = ".".join(path.relative_to(SRC).with_suffix("").parts)
        # Group by top-level subpackage (types, tasks, workflows, utils)
        parts = path.relative_to(SRC / "stargazer").parts
        section = parts[0].replace("_", " ").title() if parts else "Other"
        sections.setdefault(section, []).append(f"::: {module}")

    lines = []
    for section, directives in sections.items():
        lines += [f"## {section}", ""] + directives + [""]
    return "\n".join(lines)


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


_inject("architecture/tasks.md", catalog=_task_table("task"))
_inject("architecture/workflows.md", catalog=_task_table("workflow"))
_inject("architecture/types.md", catalog=_asset_table())
_inject("reference/api.md", api=_api_directives())
