"""
### Notebook registry consumed by the dashboard app.

Curated, hand-maintained tuple of every notebook that ships in the
`notebook-app` image, plus the helpers that read shipped notebook sources
(seeds, workflows, public snapshots) out of the installed `stargazer`
package. Workspace notebooks and a user's own snapshots are NOT here — they
live in the workspace store (`app.workspace_store`).

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import stargazer.notebooks

# Image-shipped notebooks live at /stargazer/<src/...> in the notebook pod.
# (A user's own notebooks are hydrated elsewhere; see `app.per_notebook`.)
IMAGE_WORKDIR = "/stargazer"

# The installed `stargazer.notebooks` package: the same files the notebook
# image ships under IMAGE_WORKDIR, readable from the dashboard process.
NOTEBOOKS_PKG_DIR = Path(stargazer.notebooks.__file__).parent
# Public snapshots: frozen notebooks merged upstream, shipped to everyone in
# the image like tutorials. Module attribute so tests can point it elsewhere.
PUBLIC_SNAPSHOTS_DIR = NOTEBOOKS_PKG_DIR / "snapshots"
_IMAGE_NOTEBOOKS_PREFIX = f"{IMAGE_WORKDIR}/src/stargazer/notebooks/"


# Seed notebooks shipped at `notebooks/workspace/{slug}.py`.
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
    `notebook-app` image. `section` drives which dashboard column the tile
    renders under and (with `slug`) keys the per-notebook AppEnvironment
    Knative name.
    """

    slug: str
    title: str
    description: str
    section: Literal["tutorials", "workflows"]
    path_in_image: str


# Tutorials are ordered as a reading sequence: assets → tasks → workflows →
# execution. Workflows (full pipelines) render in their own dashboard section.
NOTEBOOKS: tuple[Notebook, ...] = (
    Notebook(
        slug="assets",
        title="1. Assets",
        description="Content-addressed I/O primitives.",
        section="tutorials",
        path_in_image=f"{IMAGE_WORKDIR}/src/stargazer/notebooks/tutorials/assets.py",
    ),
    Notebook(
        slug="tasks",
        title="2. Tasks",
        description="Define a single task with typed asset I/O.",
        section="tutorials",
        path_in_image=f"{IMAGE_WORKDIR}/src/stargazer/notebooks/tutorials/tasks.py",
    ),
    Notebook(
        slug="workflows",
        title="3. Workflows",
        description="Compose tasks into a workflow with asyncio.gather fan-out.",
        section="tutorials",
        path_in_image=f"{IMAGE_WORKDIR}/src/stargazer/notebooks/tutorials/workflows.py",
    ),
    Notebook(
        slug="execution",
        title="4. Execution",
        description="Run a real workflow locally, then remote — no code changes.",
        section="tutorials",
        path_in_image=f"{IMAGE_WORKDIR}/src/stargazer/notebooks/tutorials/execution.py",
    ),
    Notebook(
        slug="scrna-pipeline",
        title="scRNA-seq",
        description="Multi-sample fan-out, clustering, side-by-side UMAPs.",
        section="workflows",
        path_in_image=f"{IMAGE_WORKDIR}/src/stargazer/notebooks/workflows/scrna_pipeline.py",
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


def slugify(name: str) -> str:
    """A name reduced to `[a-z0-9-]`: the rule Flyte app names and slugs share.

    Lowercases, turns every other character into a dash, collapses runs and
    trims the ends, so the result is also traversal-free as a filename stem.
    """
    clean = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return re.sub(r"-+", "-", clean).strip("-")


def shipped_source(path_in_image: str) -> str | None:
    """Read a shipped notebook's source by its path in the notebook image.

    The dashboard has no `/stargazer` checkout, but it installs the same package,
    so the image path maps onto the installed `stargazer.notebooks`. None if
    the path is outside it or the file is missing.
    """
    if not path_in_image.startswith(_IMAGE_NOTEBOOKS_PREFIX):
        return None
    path = NOTEBOOKS_PKG_DIR / path_in_image.removeprefix(_IMAGE_NOTEBOOKS_PREFIX)
    return path.read_text() if path.is_file() else None


def seed_source(seed: str) -> str | None:
    """The source of a create seed (`blank` or `template`), or None."""
    if seed not in SEED_SLUGS:
        return None
    path = NOTEBOOKS_PKG_DIR / "workspace" / f"{seed}.py"
    return path.read_text() if path.is_file() else None


@dataclass(frozen=True)
class PublicSnapshot:
    """A frozen notebook shipped to everyone in the image."""

    slug: str
    filename: str

    @property
    def path_in_image(self) -> str:
        """Where the notebook pod finds it."""
        return f"{_IMAGE_NOTEBOOKS_PREFIX}snapshots/{self.filename}"

    def source(self) -> str:
        """The snapshot's source, read from the installed package."""
        return (PUBLIC_SNAPSHOTS_DIR / self.filename).read_text()


def public_snapshots() -> tuple[PublicSnapshot, ...]:
    """Every shipped public snapshot, sorted by filename.

    Filenames may use underscores (they're modules); the slug is the
    launchable form.
    """
    if not PUBLIC_SNAPSHOTS_DIR.is_dir():
        return ()
    return tuple(
        PublicSnapshot(slug=slugify(p.stem), filename=p.name)
        for p in sorted(PUBLIC_SNAPSHOTS_DIR.glob("*.py"))
        if not p.name.startswith("_") and slugify(p.stem)
    )


def public_snapshot(slug: str) -> PublicSnapshot | None:
    """The shipped public snapshot with this slug, or None."""
    return next((s for s in public_snapshots() if s.slug == slug), None)
