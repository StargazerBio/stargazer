"""Inject dynamic catalog tables into static docs pages at build time.

Each target page contains a {{ catalog }} placeholder that gets replaced
with a table generated from the live registry.
"""

from pathlib import Path

import mkdocs_gen_files

from stargazer.registry import TaskRegistry
from stargazer.types import ASSET_REGISTRY

registry = TaskRegistry()
DOCS = Path(__file__).parent


def _inject(page: str, table: str) -> None:
    src = (DOCS / page).read_text()
    with mkdocs_gen_files.open(page, "w") as f:
        f.write(src.replace("{{ catalog }}", table))
    mkdocs_gen_files.set_edit_path(page, page)


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


_inject("architecture/tasks.md", _task_table("task"))
_inject("architecture/workflows.md", _task_table("workflow"))
_inject("architecture/types.md", _asset_table())
