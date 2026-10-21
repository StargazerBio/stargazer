"""
### Notebook registry consumed by the dashboard app.

Curated, hand-maintained tuple of every tutorial that ships in the
`notebook-app` image, plus the helper that reads the create seeds out of
`app/seeds/`. Workspace notebooks are NOT here — they live in the workspace
store (`app.workspace_store`). Neither are the repo's own notebooks in the
top-level `notebooks/` folder, which run from a checkout.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Image-shipped notebooks live at /stargazer/<src/...> in the notebook pod.
# (A user's own notebooks are hydrated elsewhere; see `app.per_notebook`.)
IMAGE_WORKDIR = "/stargazer"

# Seed notebooks at `app/seeds/{slug}.py`, which the dashboard installs.
SEEDS_DIR = Path(__file__).parent / "seeds"

# `/workspace/create` copies one of these under the user's chosen name. They
# are NOT rendered as dashboard tiles (only user-created notebooks are): the
# basic template is linked from the Workspace description, and both slugs are
# reserved create names + filtered out of the tile listing.
BASIC_SLUG = "basic"
BLANK_SLUG = "blank"
SEED_SLUGS = frozenset({BASIC_SLUG, BLANK_SLUG})


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
    section: Literal["tutorials"]
    path_in_image: str


# Tutorials are ordered as a reading sequence: assets → tasks → workflows →
# execution.
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


def seed_source(seed: str) -> str | None:
    """The source of a create seed (`blank` or `basic`), or None."""
    if seed not in SEED_SLUGS:
        return None
    path = SEEDS_DIR / f"{seed}.py"
    return path.read_text() if path.is_file() else None
