"""
### Marimo notebooks for interactive Stargazer workflows.

Researchers use these notebooks to explore data, run tasks, and visualize
results in a familiar Python-native environment. The hosted launch path
goes through the admin app's `/launch` handler, which spawns a
per-notebook AppEnvironment whose image is built programmatically by
`app.per_notebook.notebook_app_img`.

Also home to `nav_bar` — the navigation element each notebook renders
at the top via a one-line cell call (`nav_bar(mo, current="<slug>")`).
Renders a Dashboard link plus form-POST buttons that launch the
previous and next NAV_ORDER entries through the admin app's existing
`/launch` endpoint. `NAV_ORDER` is the canonical slug ordering and must
stay in sync with `app/notebooks.py`'s `NOTEBOOKS` tuple (the dashboard
tile registry).

spec: [docs/architecture/notebook.md](../../docs/architecture/notebook.md)
"""

import os
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class _NavEntry:
    """One ordered position in the prev/next navigation chain."""

    slug: str
    title: str
    section: Literal["tutorials", "community"]


# Canonical reading order for the nav bar's prev/next buttons. Adding a
# new tutorial means appending here AND adding a `Notebook(...)` entry
# to `app/notebooks.py::NOTEBOOKS`.
NAV_ORDER: tuple[_NavEntry, ...] = (
    _NavEntry("assets", "Assets", "tutorials"),
    _NavEntry("tasks", "Tasks", "tutorials"),
    _NavEntry("preprocessing", "Execution", "tutorials"),
    _NavEntry("scrna-pipeline", "scRNA-seq", "community"),
)


_NAV_STYLE = (
    "<style>"
    ".sg-nav { display: flex; gap: 0.5rem; align-items: center; "
    "flex-wrap: wrap; padding: 0.6rem 0; border-bottom: 1px solid #30363d; "
    "margin-bottom: 1rem; }"
    ".sg-nav-btn { display: inline-block; padding: 0.4rem 0.9rem; "
    "background: #21262d; color: #c9d1d9; border: 1px solid #30363d; "
    "border-radius: 6px; font-size: 0.85rem; cursor: pointer; "
    "text-decoration: none; font-family: inherit; }"
    ".sg-nav-btn:hover { background: #30363d; border-color: #58a6ff; }"
    ".sg-nav form { display: inline; margin: 0; }"
    "</style>"
)


def _neighbors(slug: str) -> tuple[_NavEntry | None, _NavEntry | None]:
    """Return (prev, next) entries adjacent to `slug` in NAV_ORDER."""
    for i, entry in enumerate(NAV_ORDER):
        if entry.slug == slug:
            prev = NAV_ORDER[i - 1] if i > 0 else None
            nxt = NAV_ORDER[i + 1] if i < len(NAV_ORDER) - 1 else None
            return prev, nxt
    return None, None


def _launch_form(admin_url: str, entry: _NavEntry, label: str) -> str:
    """Render one prev/next button as a form POST to admin /launch."""
    return (
        f'<form method="post" action="{admin_url}/launch">'
        f'<input type="hidden" name="slug" value="{entry.slug}">'
        f'<input type="hidden" name="section" value="{entry.section}">'
        f'<input type="hidden" name="mode" value="edit">'
        f'<button type="submit" class="sg-nav-btn">{label}</button>'
        f"</form>"
    )


def nav_bar(mo, *, current: str | None = None):
    """Render the per-notebook navigation bar.

    `current` is the current notebook's slug — pass `None` for workspace
    notebooks (only the Dashboard button is rendered then). For registered
    tutorials/community notebooks, also renders form-POST buttons that
    launch the previous and next NAV_ORDER entries via the admin app's
    `/launch` endpoint. Cross-origin POST works because the admin's
    session cookie is `SameSite=Lax`.
    """
    admin_url = os.environ.get("STARGAZER_ADMIN_URL", "").rstrip("/")
    parts = ['<a class="sg-nav-btn" href="/__sg__/dashboard">← Dashboard</a>']
    if current is not None and admin_url:
        prev, nxt = _neighbors(current)
        if prev is not None:
            parts.append(_launch_form(admin_url, prev, f"← {prev.title}"))
        if nxt is not None:
            parts.append(_launch_form(admin_url, nxt, f"{nxt.title} →"))
    return mo.Html(_NAV_STYLE + '<div class="sg-nav">' + "".join(parts) + "</div>")
