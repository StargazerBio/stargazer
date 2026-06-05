"""
### Notebook registry consumed by the dashboard app.

Curated, hand-maintained tuple of every notebook that ships in the
`notebook-app` image. Workspace notebooks are NOT listed here —
they're discovered at render time from the per-notebook pod's local
clone of the user's fork (or the GitHub Contents API as a fallback).

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

from dataclasses import dataclass
from typing import Literal


# Workspace-section paths live under /workspace/<src/...>/workspace at runtime;
# image-shipped notebooks live at /stargazer/<src/...> after the Docker COPY.
IMAGE_WORKDIR = "/stargazer"
WORKSPACE_NOTEBOOK_DIR = "/workspace/src/stargazer/notebooks/workspace"


# Seed notebooks shipped in every fork at `notebooks/workspace/{slug}.py`.
# `/workspace/create` copies one of these under the user's chosen name. They
# are NOT rendered as dashboard tiles (only user-created notebooks are): the
# template is linked from the Workspace description, and both slugs are
# reserved create names + filtered out of the tile listing.
TEMPLATE_SLUG = "template"
BLANK_SLUG = "blank"
SEED_SLUGS = frozenset({TEMPLATE_SLUG, BLANK_SLUG})


@dataclass(frozen=True)
class Notebook:
    """A single tile on the dashboard.

    `path_in_image` is the absolute path to the `.py` file inside the
    `note` image. `section` drives which dashboard column the tile
    renders under and (with `slug`) keys the per-notebook AppEnvironment
    Knative name.
    """

    slug: str
    title: str
    description: str
    section: Literal["tutorials", "community"]
    path_in_image: str


# Keep slug/section in sync with `src/stargazer/notebooks/__init__.py::NAV_ORDER`
# so the per-notebook navigation bar's prev/next buttons resolve correctly.
NOTEBOOKS: tuple[Notebook, ...] = (
    Notebook(
        slug="assets",
        title="Assets",
        description="Content-addressed I/O primitives.",
        section="tutorials",
        path_in_image=f"{IMAGE_WORKDIR}/src/stargazer/notebooks/tutorials/assets_tutorial.py",
    ),
    Notebook(
        slug="tasks",
        title="Tasks",
        description="How Stargazer tasks compose into workflows.",
        section="tutorials",
        path_in_image=f"{IMAGE_WORKDIR}/src/stargazer/notebooks/tutorials/tasks_tutorial.py",
    ),
    Notebook(
        slug="preprocessing",
        title="Execution",
        description="Asset → Task → Workflow, local vs remote on one sample.",
        section="tutorials",
        path_in_image=f"{IMAGE_WORKDIR}/src/stargazer/notebooks/tutorials/preprocessing_tutorial.py",
    ),
    Notebook(
        slug="scrna-pipeline",
        title="scRNA-seq",
        description="Multi-sample fan-out, clustering, side-by-side UMAPs.",
        section="community",
        path_in_image=f"{IMAGE_WORKDIR}/src/stargazer/notebooks/community/scrna_pipeline.py",
    ),
)


def by_slug(slug: str) -> Notebook | None:
    """Return the notebook with the given slug, or None if absent."""
    for n in NOTEBOOKS:
        if n.slug == slug:
            return n
    return None


def by_section(section: str) -> tuple[Notebook, ...]:
    """Return all notebooks belonging to one dashboard section."""
    return tuple(n for n in NOTEBOOKS if n.section == section)
