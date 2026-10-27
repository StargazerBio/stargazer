"""
### Notebook registry consumed by the dashboard app.

Curated, hand-maintained tuple of every notebook that ships in the
`notebook-app` image, plus the helpers that read shipped notebook sources
(seeds, workflows) out of the installed `stargazer` package. The asset
explorer lists the shipped notebooks as entries (`shipped_entries`), each
addressed by the CID of its file. Workspace notebooks are NOT here — they
live in the workspace store (`app.workspace_store`).

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import functools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import stargazer.notebooks
from stargazer.assets import Notebook as NotebookAsset
from stargazer.utils.cid import compute_cid

# Built-in notebooks live at /stargazer/<src/...> in the notebook pod.
# (A user's own notebooks are hydrated elsewhere; see `app.per_notebook`.)
IMAGE_WORKDIR = "/stargazer"

# The installed `stargazer.notebooks` package: the same files the notebook
# image ships under IMAGE_WORKDIR, readable from the dashboard process.
NOTEBOOKS_PKG_DIR = Path(stargazer.notebooks.__file__).parent
_IMAGE_NOTEBOOKS_PREFIX = f"{IMAGE_WORKDIR}/src/stargazer/notebooks/"


# Seed notebooks live at `src/stargazer/notebooks/templates/{slug}.py`.
# `/workspace/create` copies one of these under the user's chosen name. They
# are NOT rendered as dashboard tiles (only user-created notebooks are): the
# basic template is linked from the Workspace description, and both slugs are
# reserved create names + filtered out of the tile listing.
BASIC_SLUG = "basic"
BLANK_SLUG = "blank"
SEED_SLUGS = frozenset({BASIC_SLUG, BLANK_SLUG})


@dataclass(frozen=True)
class Notebook:
    """A notebook shipped in the `notebook-app` image.

    `path_in_image` is the notebook's absolute `.py` path in the image.
    `section` is its kind, which the explorer shows as its `category` and a
    launch names; `slug` names its app (`nb-<slug>-<mode>`).
    """

    slug: str
    title: str
    description: str
    section: Literal["tutorials", "workflows"]
    path_in_image: str


# Tutorials are ordered as a reading sequence: assets → tasks → workflows →
# execution, the order the explorer lists them in. Workflows are full pipelines.
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


def _package_path(path_in_image: str) -> Path | None:
    """A shipped notebook's file in the installed package, or None if outside it."""
    if not path_in_image.startswith(_IMAGE_NOTEBOOKS_PREFIX):
        return None
    return NOTEBOOKS_PKG_DIR / path_in_image.removeprefix(_IMAGE_NOTEBOOKS_PREFIX)


@functools.cache
def shipped_entries() -> tuple[dict, ...]:
    """The shipped notebooks as asset explorer entries, worked out once.

    Each is shaped like a listed record, with `source` `stargazer`: its CID
    is its file's, and its keyvalues a `Notebook` asset's plus `category`,
    `tutorial` or `workflow` after its section. Nothing stores them; they're
    read from the installed package.
    """
    entries = []
    for nb in NOTEBOOKS:
        path = _package_path(nb.path_in_image)
        keyvalues = NotebookAsset(
            title=nb.title, description=nb.description, slug=nb.slug
        ).to_keyvalues()
        entries.append(
            {
                "cid": compute_cid(path),
                "name": path.name,
                "source": "stargazer",
                "keyvalues": {**keyvalues, "category": nb.section.removesuffix("s")},
            }
        )
    return tuple(entries)


def shipped_path(cid: str) -> Path | None:
    """The file of the shipped notebook whose CID is `cid`, or None."""
    for nb, entry in zip(NOTEBOOKS, shipped_entries(), strict=True):
        if entry["cid"] == cid:
            return _package_path(nb.path_in_image)
    return None


def slugify(name: str) -> str:
    """A name reduced to `[a-z0-9-]`: the rule Flyte app names and slugs share.

    Lowercases, turns every other character into a dash, collapses runs and
    trims the ends, so the result is also traversal-free as a filename stem.
    """
    clean = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return re.sub(r"-+", "-", clean).strip("-")


def builtin_source(path_in_image: str) -> str | None:
    """Read a built-in notebook's source by its path in the notebook image.

    The dashboard has no `/stargazer` checkout, but it installs the same package,
    so the image path maps onto the installed `stargazer.notebooks`. None if
    the path is outside it or the file is missing.
    """
    path = _package_path(path_in_image)
    return path.read_text() if path and path.is_file() else None


def seed_source(seed: str) -> str | None:
    """The source of a create seed (`blank` or `basic`), or None."""
    if seed not in SEED_SLUGS:
        return None
    path = NOTEBOOKS_PKG_DIR / "templates" / f"{seed}.py"
    return path.read_text() if path.is_file() else None
