"""
### Stargazer admin app — the dashboard and notebook launcher.

Shared, single deployment behind Union's login (`requires_auth=True`). Union
owns sign-in and forwards the signed-in user on every request (see
`app.identity`); there is no OAuth flow, session cookie, or GitHub
integration here. It has three jobs:

1. **Per-user dashboard.** Renders the notebook tile sections: Workflows and
   Tutorials (shipped in the per-notebook image), Snapshots (shipped public
   ones plus the user's own), and Workspace (the user's own notebooks). A
   user's notebooks live in the workspace store (`app.workspace_store`),
   keyed by their Union subject, so saving needs no setup. The first request
   from a user ensures their Flyte project exists (`app.provision`).

2. **Workspace actions.** Create, settings, delete, snapshot (freeze), copy
   and download, all against the workspace store.

3. **Launch broker.** `POST /launch` builds a per-notebook AppEnvironment via
   `app.per_notebook.per_notebook_env(...)`, owned by the user, serves it into
   their project, and returns its URL. The admin never calls a notebook pod:
   the pod hydrates and saves its own workspace and shows its own starting
   page while it warms up.

`app_env` (this app's own AppEnvironment) and `main()` (the deploy
entrypoint) are also defined here.

Local development (identity comes from the `X-User-*` headers Union would set):
    uvicorn app.admin_app:asgi_app --reload --port 8080

Deploy hosted to Flyte:
    python -m app.admin_app           # or: stargazer-app

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import asyncio
import atexit
import os
import socket
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path

import flyte
import flyte.app
from fastapi import FastAPI, Form, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from flyte._initialize import get_init_config
from flyte.remote import App

from app import config, provision
from app import workspace_store as store
from app.assets import router as assets_router
from app.identity import CurrentUser, User
from app.init import init
from app.notebook_meta import (
    DEFAULT_RESOURCES,
    NotebookResources,
    memory_to_gib,
    parse_notebook_description,
    parse_notebook_name,
    parse_notebook_resources,
    resources_from_inputs,
    with_stargazer_resources,
)
from app.notebooks import (
    SEED_SLUGS,
    Notebook,
    by_section,
    by_slug,
    public_snapshot,
    public_snapshots,
    seed_source,
    shipped_source,
    slugify,
)
from app.per_notebook import (
    SNAPSHOT_NOTEBOOK_DIR,
    WORKSPACE_NOTEBOOK_DIR,
    list_project_apps,
    notebook_app_img_recipe,
    per_notebook_env,
)
from app.templates import templates
from stargazer.config import (
    PROJECT_ROOT,
    STARGAZER_ENV_VARS,
    logger,
)

# ---------------------------------------------------------------------------
# Flyte AppEnvironment for the admin app itself.
# ---------------------------------------------------------------------------

# AppEnvironment `secrets=[...]` is silently dropped on App pods in this Flyte
# build, so the one secret the admin needs is baked from the deployer's shell
# into `env_vars` (the value then lives in the App spec). Optional: without it
# the asset manager renders a "not configured" state.
# See .opencode/reference/devbox_workarounds.md
_RUNTIME_SECRETS = {
    name: os.environ[name] for name in ("PINATA_JWT",) if os.environ.get(name)
}

# Admin pod needs a default Flyte project for code-bundle uploads during
# per-user `serve.aio(per_notebook_env)` calls. `with_servecontext(project=...)`
# alone is not enough — the upload uses the client's init-time project.
_FLYTE_CONTEXT = {
    "FLYTE_PROJECT": config.FLYTE_PROJECT,
    "FLYTE_DOMAIN": config.FLYTE_DOMAIN,
}

# Non-secret config request handlers read at runtime, baked into the pod env so
# the deployed admin sees what the deployer's shell set. The workspace root
# must match what notebook pods hydrate from and save to.
_PUBLIC_CONFIG = (
    {"STARGAZER_WORKSPACE_ROOT": config.WORKSPACE_ROOT} if config.WORKSPACE_ROOT else {}
)


app_env = flyte.app.AppEnvironment(
    name="admin-app",
    description="Stargazer dashboard and notebook launcher",
    image=(
        flyte.Image.from_debian_base(
            name="admin-app",
            registry=os.environ.get("STARGAZER_REGISTRY"),
            platform=("linux/amd64", "linux/arm64"),
        )
        .with_apt_packages("ca-certificates")
        .with_uv_project(
            PROJECT_ROOT / "pyproject.toml",
            project_install_mode="install_project",
            extra_args="--extra landing",
        )
        .with_commands(["flyte create config --local-persistence"])
    ),
    args=[
        "uvicorn",
        "app.admin_app:asgi_app",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
    ],
    port=8080,
    # Union's login gates every request and forwards the user's identity.
    requires_auth=True,
    resources=flyte.Resources(memory=("512Mi", "1Gi")),
    env_vars={
        **STARGAZER_ENV_VARS,
        **_RUNTIME_SECRETS,
        **_FLYTE_CONTEXT,
        **_PUBLIC_CONFIG,
    },
    # Flyte's loaded_modules bundler ships only .py files; HTML and the
    # landing-page logo must be enumerated.
    include=("templates/", "static/"),
)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Init the Flyte client at startup so /launch can call `flyte.serve.aio()`."""
    init()
    yield


class _RevalidatingStatic(StaticFiles):
    """StaticFiles that forces conditional revalidation on every request.

    Flyte's code bundle unpacks files with a fixed 1981 mtime, and stock
    StaticFiles sends no Cache-Control — so browsers apply *heuristic*
    freshness (~10% of now-minus-last-modified, years from a 1981 date) and
    keep serving a stale asset after a redeploy changes it.
    `Cache-Control: no-cache` means "store but always revalidate"; the
    response already carries an ETag, so this is a cheap 304 when unchanged
    and a fresh 200 once a redeploy changes the file. See
    devbox_workarounds.md.
    """

    def file_response(self, *args, **kwargs):
        """Return the stock file response with `Cache-Control: no-cache` set."""
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


asgi_app = FastAPI(title="Stargazer", docs_url=None, redoc_url=None, lifespan=lifespan)
# The dashboard HTML and the asset listings compress well; tiny responses
# (health checks, redirects) are left alone.
asgi_app.add_middleware(GZipMiddleware, minimum_size=1024)
asgi_app.mount(
    "/static",
    _RevalidatingStatic(directory=str(Path(__file__).parent / "static")),
    name="static",
)
asgi_app.include_router(assets_router)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STORE_OFF = "saving notebooks isn't available on this deployment"


def _store_ready() -> bool:
    """Whether this deploy has a workspace store to save notebooks in."""
    return bool(config.WORKSPACE_ROOT)


def _store_off() -> JSONResponse:
    """The 503 every store-backed route returns without a store."""
    return JSONResponse({"error": _STORE_OFF}, status_code=503)


def _parse_nb_name(name: str) -> tuple[str, str] | None:
    """Split a per-notebook app name `nb-{slug}-{mode}` into `(slug, mode)`.

    Slugs may themselves contain dashes, so the mode is the *last* segment and
    must be a real mode. Returns None for anything that isn't a per-notebook
    app deployment (other services in the project are ignored).
    """
    if not name.startswith("nb-"):
        return None
    slug, _, mode = name.removeprefix("nb-").rpartition("-")
    if not slug or mode not in ("edit", "run"):
        return None
    return slug, mode


def _notebook_slug(name: str) -> str | None:
    """Derive a filename slug from a notebook name that is also a valid pod name.

    The slug is both the filename stem and the pod name (`nb-{slug}-{mode}`),
    and Flyte app names allow only `[a-z0-9-]`. The original name is preserved
    verbatim as the display title (stored in the notebook header — see
    `parse_notebook_name`). Returns None when the result is empty or collides
    with a reserved seed slug (`SEED_SLUGS`).
    """
    slug = slugify(name)
    if not slug or slug in SEED_SLUGS:
        return None
    return slug


def _tile_dict(
    slug: str,
    title: str,
    description: str,
    section: str,
    *,
    cpu: int | None = None,
    memory: int | None = None,
    source: str | None = None,
) -> dict:
    """Build the context dict consumed by `_tile.html`.

    `source` is what launch/copy/download send as `section`: it differs from
    the rendered `section` only for shipped public snapshots, which render in
    Snapshots but come from the image (`public-snapshots`). `cpu`/`memory`
    (whole GiB) are carried only for workspace tiles — they seed the settings
    modal's fields via the gear button's data attributes.
    """
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "section": section,
        "source": source or section,
        "cpu": cpu,
        "memory": memory,
    }


def _display_name(filename: str) -> str:
    """Human-friendly tile title for a notebook file.

    Drops the `.py` extension and capitalizes the first letter, so
    `my-notebook.py` tiles as `My-notebook`.
    """
    stem = filename.removesuffix(".py")
    return stem[:1].upper() + stem[1:]


_GENERIC_WS_DESC = "Personal workspace notebook."


def _workspace_tile_dict(
    slug: str, cpu: int, memory: int, description: str, name: str = ""
) -> dict:
    """A workspace tile carrying its editable resources + blurb for the modal.

    `name` is the title the user typed at creation, preserved verbatim; when
    absent the title falls back to a filename-derived form.
    """
    return _tile_dict(
        slug,
        name or _display_name(f"{slug}.py"),
        description or _GENERIC_WS_DESC,
        "workspace",
        cpu=cpu,
        memory=memory,
    )


def _snapshot_tile_dict(slug: str, *, public: bool = False) -> dict:
    """A read-only Snapshots tile — a frozen record, runnable only in run mode."""
    return _tile_dict(
        slug,
        _display_name(f"{slug}.py"),
        "",
        "snapshots",
        source="public-snapshots" if public else "snapshots",
    )


async def _workspace_tiles(user: User) -> list[dict]:
    """Build Workspace tiles from the user's own notebooks in the store.

    Each notebook's `[tool.stargazer]` header is read (in parallel,
    best-effort) so the tile shows its description and the gear seeds the
    settings modal with current resources. A failed read falls back to the
    generic blurb + default resources rather than dropping the tile.
    """
    try:
        files = await store.list_workspace(user.subject)
    except Exception as exc:
        logger.warning(f"Workspace listing failed for {user.subject!r}: {exc}")
        return []
    slugs = [s for f in files if (s := f.removesuffix(".py")) not in SEED_SLUGS]
    default_gib = memory_to_gib(DEFAULT_RESOURCES.memory)

    async def _tile(slug: str) -> dict:
        """Build one workspace tile, parsing its header (best-effort)."""
        cpu, memory, desc, name = DEFAULT_RESOURCES.cpu, default_gib, "", ""
        try:
            src = await store.get_workspace_notebook(user.subject, f"{slug}.py")
            if src:
                res = parse_notebook_resources(src)
                cpu, memory = res.cpu, memory_to_gib(res.memory)
                desc = parse_notebook_description(src)
                name = parse_notebook_name(src)
        except Exception as exc:
            logger.warning(f"Workspace metadata read failed for {slug!r}: {exc}")
        return _workspace_tile_dict(slug, cpu, memory, desc, name=name)

    return list(await asyncio.gather(*[_tile(s) for s in slugs]))


async def _snapshot_tiles(user: User) -> list[dict]:
    """Shipped public snapshots, then the user's own, as Snapshots tiles."""
    tiles = [_snapshot_tile_dict(s.slug, public=True) for s in public_snapshots()]
    if _store_ready():
        try:
            own = await store.list_snapshots(user.subject)
        except Exception as exc:
            logger.warning(f"Snapshot listing failed for {user.subject!r}: {exc}")
            own = []
        tiles += [_snapshot_tile_dict(f.removesuffix(".py")) for f in own]
    return tiles


async def _teardown_notebook_pods(user: User, slug: str) -> None:
    """Completely tear down each edit/run pod for a notebook slug.

    Deactivate first (a clean stop), then delete the deployment record, so the
    notebook leaves nothing behind — no tile to Stop it, no orphan for
    `/workspace/cleanup` to reap. Shared by every route that removes a
    notebook from the dashboard. Every step is best-effort and never raises.
    """
    project = provision.project_id(user.subject)
    for mode in ("edit", "run"):
        name = f"nb-{slug}-{mode}"
        try:
            app = await App.get.aio(
                name=name, project=project, domain=config.FLYTE_DOMAIN
            )
            await app.deactivate.aio()
        except Exception:
            pass
        try:
            await App.delete.aio(name=name, project=project, domain=config.FLYTE_DOMAIN)
        except Exception:
            pass


def _invalid_slug(slug: str) -> JSONResponse | None:
    """A 400 for a slug that isn't a user notebook's, else None."""
    if _notebook_slug(slug) != slug:
        return JSONResponse(
            {"error": f"invalid or reserved notebook: {slug!r}"}, status_code=400
        )
    return None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@asgi_app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: CurrentUser):
    """Render the signed-in user's dashboard."""
    provision_error = False
    try:
        await provision.provision_user(user)
    except Exception as exc:
        logger.error(f"Provisioning failed for {user.subject!r}: {exc}")
        provision_error = True

    workspace, snapshots = await asyncio.gather(
        _workspace_tiles(user) if _store_ready() else asyncio.sleep(0, []),
        _snapshot_tiles(user),
    )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Dashboard",
            "user": user,
            "workspace_configured": _store_ready(),
            "provision_error": provision_error,
            "tutorials": [
                _tile_dict(n.slug, n.title, n.description, "tutorials")
                for n in by_section("tutorials")
            ],
            "workflows": [
                _tile_dict(n.slug, n.title, n.description, "workflows")
                for n in by_section("workflows")
            ],
            "snapshots": snapshots,
            "workspace": workspace,
        },
    )


# ---------------------------------------------------------------------------
# Workspace actions
# ---------------------------------------------------------------------------


def _render_tile(tile: dict) -> str:
    """Render one tile's HTML for the dashboard JS to insert."""
    return templates.env.get_template("_tile.html").render(tile=tile)


@asgi_app.post("/workspace/create")
async def workspace_create(
    user: CurrentUser,
    name: str = Form(...),
    source: str = Form("blank"),
    cpu: str = Form("2"),
    memory: str = Form("4"),
):
    """Create a new workspace notebook from the blank or template seed.

    Writes `<slug>.py` to the user's store with default resources baked into
    its `[tool.stargazer]` header, then returns the rendered tile. Resources
    (and the tile blurb) are edited afterward via the tile's gear → settings
    modal (`/workspace/settings`). Create stays a pure "add a notebook"
    action: no launch, no navigation.
    """
    if not _store_ready():
        return _store_off()
    if source not in SEED_SLUGS:
        return JSONResponse({"error": f"invalid source: {source}"}, status_code=400)
    slug = _notebook_slug(name)
    if slug is None:
        return JSONResponse(
            {"error": f"invalid or reserved notebook name: {name!r}"}, status_code=400
        )

    # The title the user typed, preserved verbatim (whitespace collapsed) for
    # the tile; the slug above is the lowercased, dash-joined filename form.
    display_name = " ".join(name.split())
    filename = f"{slug}.py"
    resources = resources_from_inputs(cpu, memory)
    seed = seed_source(source)
    if seed is None:
        return JSONResponse({"error": f"{source} seed not found"}, status_code=500)
    content = with_stargazer_resources(seed, resources, name=display_name)
    try:
        await store.create_workspace_notebook(user.subject, filename, content)
    except store.NotebookExistsError:
        return JSONResponse(
            {"error": f"notebook already exists: {filename}"}, status_code=409
        )
    except Exception as exc:
        logger.error(f"Notebook create failed for {filename!r}: {exc}")
        return JSONResponse({"error": f"create failed: {exc}"}, status_code=502)

    tile = _workspace_tile_dict(
        slug, resources.cpu, memory_to_gib(resources.memory), "", name=display_name
    )
    return JSONResponse({"slug": slug, "tile_html": _render_tile(tile)})


async def _copy_source(user: User, slug: str, section: str) -> tuple[str, str, str]:
    """Resolve a copy source to `(source, default_title, default_description)`.

    Raises `LookupError` when the source doesn't exist and `ValueError` for a
    section that can't be copied from.
    """
    if section == "workflows":
        nb = by_slug(slug)
        source = shipped_source(nb.path_in_image) if nb else None
        if nb is None or nb.section != "workflows" or source is None:
            raise LookupError(f"unknown workflow: {slug}")
        return source, nb.title, nb.description
    if section == "public-snapshots":
        snap = public_snapshot(slug)
        if snap is None:
            raise LookupError(f"unknown snapshot: {slug}")
        source = snap.source()
    elif section == "snapshots":
        if _notebook_slug(slug) != slug:
            raise ValueError(f"invalid notebook: {slug!r}")
        source = await store.get_snapshot_notebook(user.subject, f"{slug}.py")
        if source is None:
            raise LookupError(f"source notebook not found: {slug}")
    else:
        raise ValueError(f"cannot copy from section: {section}")
    title = parse_notebook_name(source) or _display_name(f"{slug}.py")
    return source, title, parse_notebook_description(source)


@asgi_app.post("/workspace/copy")
async def workspace_copy(
    user: CurrentUser, slug: str = Form(...), section: str = Form(...)
):
    """Copy a Workflows or Snapshots notebook into the user's workspace.

    The source is a shipped Workflows notebook, a shipped public snapshot, or
    one of the user's own snapshots; it's written as a fresh, editable
    workspace notebook. The copy keeps the source's `[tool.stargazer]`
    resources but gets its own name/description so it tiles like any other
    workspace notebook. The target slug is derived from the source title;
    like `/workspace/create` it fails with 409 if that name is taken. Returns
    the rendered Workspace tile.
    """
    if not _store_ready():
        return _store_off()
    try:
        source, title, desc = await _copy_source(user, slug, section)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except LookupError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)

    target_slug = _notebook_slug(title)
    if target_slug is None:
        return JSONResponse(
            {"error": f"could not derive a notebook name from {title!r}"},
            status_code=400,
        )
    filename = f"{target_slug}.py"
    resources = parse_notebook_resources(source)
    content = with_stargazer_resources(
        source, resources, description=desc or None, name=title
    )
    try:
        await store.create_workspace_notebook(user.subject, filename, content)
    except store.NotebookExistsError:
        return JSONResponse(
            {"error": f"notebook already exists: {filename}"}, status_code=409
        )
    except Exception as exc:
        logger.error(f"Notebook copy failed for {slug!r} from {section}: {exc}")
        return JSONResponse({"error": f"copy failed: {exc}"}, status_code=502)

    tile = _workspace_tile_dict(
        target_slug, resources.cpu, memory_to_gib(resources.memory), desc, name=title
    )
    return JSONResponse({"slug": target_slug, "tile_html": _render_tile(tile)})


@asgi_app.post("/workspace/settings")
async def workspace_settings(
    user: CurrentUser,
    slug: str = Form(...),
    cpu: str = Form(...),
    memory: str = Form(...),
    description: str = Form(""),
):
    """Persist edited resources + description for a workspace notebook.

    Rewrites the notebook's `[tool.stargazer]` header (cpu/memory + the tile
    blurb). Resource changes take effect at the **next** `/launch` (resources
    bind at pod-spawn); the description is reflected on the tile immediately.
    Returns the normalized values so the browser can refresh the tile + gear
    data in place.
    """
    if not _store_ready():
        return _store_off()
    if bad := _invalid_slug(slug):
        return bad
    filename = f"{slug}.py"
    resources = resources_from_inputs(cpu, memory)
    desc = " ".join(description.split())[:200]
    try:
        source = await store.get_workspace_notebook(user.subject, filename)
        if source is None:
            return JSONResponse(
                {"error": f"notebook not found: {filename}"}, status_code=404
            )
        # Rewrites the whole table — re-pass the stored display name so this
        # resources/description edit doesn't drop it.
        content = with_stargazer_resources(
            source,
            resources,
            description=desc or None,
            name=parse_notebook_name(source) or None,
        )
        await store.update_workspace_notebook(user.subject, filename, content)
    except Exception as exc:
        logger.error(f"Notebook settings update failed for {filename!r}: {exc}")
        return JSONResponse({"error": f"update failed: {exc}"}, status_code=502)

    return JSONResponse(
        {
            "slug": slug,
            "cpu": resources.cpu,
            "memory": memory_to_gib(resources.memory),
            "description": desc or _GENERIC_WS_DESC,
        }
    )


@asgi_app.post("/workspace/delete")
async def workspace_delete(user: CurrentUser, slug: str = Form(...)):
    """Delete a workspace notebook and tear down its pods.

    Idempotent — a notebook that's already gone still returns 200. Teardown
    is best-effort and never fails the delete.
    """
    if not _store_ready():
        return _store_off()
    if bad := _invalid_slug(slug):
        return bad
    await _teardown_notebook_pods(user, slug)
    try:
        await store.delete_workspace_notebook(user.subject, f"{slug}.py")
    except Exception as exc:
        logger.error(f"Notebook delete failed for {slug!r}: {exc}")
        return JSONResponse({"error": f"delete failed: {exc}"}, status_code=502)
    return JSONResponse({"status": "deleted", "slug": slug})


@asgi_app.post("/workspace/snapshot")
async def workspace_snapshot(user: CurrentUser, slug: str = Form(...)):
    """Freeze a workspace notebook by *moving* it into the user's snapshots.

    The notebook's current stored source (what its pod last saved) is
    re-created verbatim as a snapshot, then the workspace original is
    deleted. The snapshot write happens first, so a failed move leaves the
    notebook editable rather than lost. A slug shared with a shipped public
    snapshot is refused, since both would launch as the same pod. Tears down
    any running pod for the slug — once moved, no Workspace tile remains to
    Stop it.
    """
    if not _store_ready():
        return _store_off()
    if bad := _invalid_slug(slug):
        return bad
    if public_snapshot(slug) is not None:
        return JSONResponse(
            {"error": f"a published snapshot is already named {slug!r}; rename first"},
            status_code=409,
        )
    filename = f"{slug}.py"
    try:
        source = await store.get_workspace_notebook(user.subject, filename)
        if source is None:
            return JSONResponse(
                {"error": f"notebook not found: {filename}"}, status_code=404
            )
        await store.create_snapshot_notebook(user.subject, filename, source)
        await store.delete_workspace_notebook(user.subject, filename)
    except store.NotebookExistsError:
        return JSONResponse(
            {"error": f"a snapshot named {filename} already exists"}, status_code=409
        )
    except Exception as exc:
        logger.error(f"Notebook snapshot failed for {slug!r}: {exc}")
        return JSONResponse({"error": f"snapshot failed: {exc}"}, status_code=502)

    await _teardown_notebook_pods(user, slug)
    tile_html = _render_tile(_snapshot_tile_dict(slug))
    return JSONResponse({"status": "snapshotted", "slug": slug, "tile_html": tile_html})


@asgi_app.post("/snapshot/delete")
async def snapshot_delete(user: CurrentUser, slug: str = Form(...)):
    """Delete one of the user's own snapshots and tear down its run pod.

    Idempotent. Shipped public snapshots aren't the user's to delete.
    """
    if not _store_ready():
        return _store_off()
    if bad := _invalid_slug(slug):
        return bad
    await _teardown_notebook_pods(user, slug)
    try:
        await store.delete_snapshot_notebook(user.subject, f"{slug}.py")
    except Exception as exc:
        logger.error(f"Snapshot delete failed for {slug!r}: {exc}")
        return JSONResponse({"error": f"delete failed: {exc}"}, status_code=502)
    return JSONResponse({"status": "deleted", "slug": slug})


@asgi_app.get("/workspace/download")
async def workspace_download(user: CurrentUser, slug: str, section: str = "workspace"):
    """Download a notebook's `.py` source as an attachment.

    Covers the user's workspace notebooks and own snapshots (from the store)
    and shipped public snapshots (from the image). This is the path for
    sharing a notebook upstream: download it and contribute it like any file.
    """
    if section == "public-snapshots":
        snap = public_snapshot(slug)
        if snap is None:
            return JSONResponse({"error": "notebook not found"}, status_code=404)
        source, filename = snap.source(), snap.filename
    elif section in ("workspace", "snapshots"):
        if not _store_ready():
            return _store_off()
        if bad := _invalid_slug(slug):
            return bad
        filename = f"{slug}.py"
        read = (
            store.get_workspace_notebook
            if section == "workspace"
            else store.get_snapshot_notebook
        )
        source = await read(user.subject, filename)
        if source is None:
            return JSONResponse({"error": "notebook not found"}, status_code=404)
    else:
        return JSONResponse({"error": f"invalid section: {section}"}, status_code=400)
    return Response(
        source,
        media_type="text/x-python; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Launch / stop / status / cleanup
# ---------------------------------------------------------------------------

_SECTIONS = ("tutorials", "workflows", "workspace", "snapshots", "public-snapshots")


async def _launch_target(
    user: User, slug: str, section: str
) -> tuple[str, NotebookResources | None] | None:
    """Resolve a launch to `(notebook_path, resources)`, or None if unknown.

    Store-backed notebooks (workspace, own snapshots) and shipped public
    snapshots declare resources in their `[tool.stargazer]` header; a missing
    or unreadable header falls back to the defaults. Tutorials and workflows
    keep the env's legacy defaults (`resources=None`).
    """
    if section in ("workspace", "snapshots"):
        if section == "workspace":
            notebook_dir, read = WORKSPACE_NOTEBOOK_DIR, store.get_workspace_notebook
        else:
            notebook_dir, read = SNAPSHOT_NOTEBOOK_DIR, store.get_snapshot_notebook
        try:
            source = await read(user.subject, f"{slug}.py")
        except Exception as exc:
            logger.warning(f"Resource read failed for {section} {slug!r}: {exc}")
            source = None
        resources = parse_notebook_resources(source) if source else DEFAULT_RESOURCES
        return f"{notebook_dir}/{slug}.py", resources
    if section == "public-snapshots":
        snap = public_snapshot(slug)
        if snap is None:
            return None
        return snap.path_in_image, parse_notebook_resources(snap.source())
    nb: Notebook | None = by_slug(slug)
    if nb is None or nb.section != section:
        return None
    return nb.path_in_image, None


@asgi_app.post("/launch")
async def launch(
    request: Request,
    user: CurrentUser,
    slug: str = Form(...),
    mode: str = Form(...),
    section: str = Form(...),
):
    """Spawn (or reuse) the user's per-notebook app for slug+mode; return its URL.

    The pod is owned by the user (only they get past its proxy), hydrates and
    saves its own workspace, and shows a starting page until the notebook is
    ready, so the URL is returned as soon as the app is admitted.
    """
    if mode not in ("edit", "run"):
        return JSONResponse({"error": f"invalid mode: {mode}"}, status_code=400)
    if section not in _SECTIONS:
        return JSONResponse({"error": f"invalid section: {section}"}, status_code=400)
    if section in ("snapshots", "public-snapshots") and mode != "run":
        return JSONResponse(
            {"error": "snapshots open in run mode only"}, status_code=400
        )
    if section in ("workspace", "snapshots"):
        if not _store_ready():
            return _store_off()
        if bad := _invalid_slug(slug):
            return bad

    target = await _launch_target(user, slug, section)
    if target is None:
        return JSONResponse({"error": f"unknown notebook: {slug}"}, status_code=404)
    notebook_path, resources = target

    try:
        project = await provision.provision_user(user)
    except Exception as exc:
        logger.error(f"Provisioning failed for {user.subject!r}: {exc}")
        return JSONResponse(
            {"error": "your workspace isn't ready yet; please retry in a moment"},
            status_code=503,
        )

    env = per_notebook_env(
        slug=slug,
        mode=mode,
        notebook_path=notebook_path,
        owner_subject=user.subject,
        admin_url=str(request.base_url).rstrip("/"),
        resources=resources,
    )
    env.env_vars["FLYTE_PROJECT"] = project
    # App pods aren't given the org (task pods get `_U_ORG_NAME`); pass ours on
    # so in-pod SDK calls address the tenant's org.
    if os.environ.get("FLYTE_ORG"):
        env.env_vars["FLYTE_ORG"] = os.environ["FLYTE_ORG"]
    # Owner attribution: workspace MCP/SDK uploads stamp `_owner` from this
    # (and config.py forwards it onward into task pods at run submission).
    env.env_vars["STARGAZER_OWNER"] = user.subject

    # `serve.aio()` watches the deployment to readiness and raises if the pod
    # is slow to schedule/boot. That's not a real failure: the route (and
    # `App.endpoint`) exist as soon as the app is admitted, and the pod shows
    # its own starting page. So on a watch error, recover the endpoint and
    # hand it back anyway; only error out if the app genuinely isn't there.
    try:
        deployment = await flyte.with_servecontext(
            project=project, domain=config.FLYTE_DOMAIN
        ).serve.aio(env)
        endpoint = deployment.endpoint
    except Exception as exc:
        logger.warning(f"serve watch unconfirmed for {slug!r}/{mode!r}: {exc}")
        try:
            app = await App.get.aio(
                name=f"nb-{slug}-{mode}", project=project, domain=config.FLYTE_DOMAIN
            )
            endpoint = app.endpoint
        except Exception:
            endpoint = None
        if not endpoint:
            return JSONResponse(
                {"error": "notebook is still starting; please retry in a moment"},
                status_code=503,
            )
    return JSONResponse({"url": endpoint})


@asgi_app.post("/stop")
async def stop(user: CurrentUser, slug: str = Form(...), mode: str = Form(...)):
    """Deactivate the user's per-notebook app for the requested slug+mode."""
    if mode not in ("edit", "run"):
        return JSONResponse({"error": f"invalid mode: {mode}"}, status_code=400)
    project = provision.project_id(user.subject)
    name = f"nb-{slug}-{mode}"
    try:
        app = await App.get.aio(name=name, project=project, domain=config.FLYTE_DOMAIN)
        await app.deactivate.aio()
    except Exception as exc:
        logger.error(f"Stop failed for {name!r} in {project!r}: {exc}")
        return JSONResponse({"error": f"stop failed: {exc}"}, status_code=502)
    return JSONResponse({"stopped": True})


@asgi_app.get("/launch/status")
async def launch_status(user: CurrentUser):
    """Report which of the user's notebooks have an active per-notebook app.

    Discovery is one control-plane list (`list_project_apps`, the same call
    `/workspace/cleanup` uses) of every deployment in the user's project,
    filtered to `nb-{slug}-{mode}` names. Each is then re-fetched with
    `App.get` (in parallel) for authoritative status, since a list payload may
    not carry full conditions, and the active ones are returned with their
    endpoints. Read live from the control plane, so it survives admin
    restarts. The dashboard calls this on load to render running notebooks
    straight to Open+Stop.
    """
    project = provision.project_id(user.subject)
    try:
        apps = await list_project_apps(project, domain=config.FLYTE_DOMAIN)
    except Exception as exc:
        logger.warning(f"status listing failed for {project!r}: {exc}")
        return JSONResponse({"running": []})
    candidates = [
        (app.name, parsed) for app in apps if (parsed := _parse_nb_name(app.name))
    ]

    async def _probe(name: str, slug: str, mode: str) -> dict | None:
        """Return run info for a discovered app if it's active, else None."""
        try:
            app = await App.get.aio(
                name=name, project=project, domain=config.FLYTE_DOMAIN
            )
        except Exception:
            return None  # vanished between list and get
        if app.is_active() and app.endpoint:
            return {"slug": slug, "mode": mode, "url": app.endpoint}
        return None

    probes = [_probe(name, slug, mode) for name, (slug, mode) in candidates]
    running = [r for r in await asyncio.gather(*probes) if r is not None]
    return JSONResponse({"running": running})


@asgi_app.post("/workspace/cleanup")
async def workspace_cleanup(user: CurrentUser):
    """Delete the user's stopped (deactivated) per-notebook app deployments.

    Stopping a notebook deactivates its app but leaves the deployment record.
    This lists EVERY `nb-*` app in the user's project — not just those still
    on the dashboard — and removes the deactivated ones. Each is re-fetched
    with `App.get` for authoritative status before deletion; active apps are
    left alone. Returns the deleted names.
    """
    project = provision.project_id(user.subject)
    try:
        apps = await list_project_apps(project, domain=config.FLYTE_DOMAIN)
    except Exception as exc:
        logger.error(f"cleanup listing failed for {project!r}: {exc}")
        return JSONResponse({"error": f"cleanup failed: {exc}"}, status_code=502)

    names = [app.name for app in apps if app.name.startswith("nb-")]

    async def _cleanup(name: str) -> str | None:
        """Delete `name` if it's still a deactivated deployment."""
        try:
            app = await App.get.aio(
                name=name, project=project, domain=config.FLYTE_DOMAIN
            )
        except Exception:
            return None  # vanished between list and get
        if not app.is_deactivated():
            return None
        try:
            await App.delete.aio(name=name, project=project, domain=config.FLYTE_DOMAIN)
            return name
        except Exception as exc:
            logger.warning(f"cleanup delete failed for {name!r}: {exc}")
            return None

    results = await asyncio.gather(*(_cleanup(name) for name in names))
    deleted = [r for r in results if r is not None]
    return JSONResponse({"deleted": deleted, "count": len(deleted)})


@asgi_app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Deploy entrypoint
# ---------------------------------------------------------------------------


def _build_notebook_image() -> str:
    """Build the per-notebook image recipe and return its content-hashed URI.

    The admin pod can't build images (no Docker daemon, no project layout), so
    the deployer builds here and `main()` bakes the URI into the admin pod as
    `STARGAZER_NOTEBOOK_IMAGE`; every per-notebook app then runs exactly this
    build. The builder comes from the Flyte config: local docker pushing to the
    devbox registry, or Union's remote builder pushing to Union's registry.
    """
    logger.info("Building per-notebook flyte.Image (recipe)")
    result = flyte.build(notebook_app_img_recipe)
    if result.uri is None:
        raise RuntimeError("flyte.build did not return an image URI")
    logger.info(f"Per-notebook image: {result.uri}")
    return result.uri


def _start_storage_port_forward() -> None:
    """Open `localhost:9000 → svc/rustfs-svc:9000` for devbox deploys.

    `flyte-binary` returns signed upload URLs with host `rustfs-svc.flyte:9000`
    (so admin App pods can reach storage via k8s DNS, matching production
    behaviour). On the deployer's laptop that hostname only works if it
    resolves to `127.0.0.1` (NAS DNS or `/etc/hosts`) AND there's a
    port-forward to the in-cluster service.

    Devbox only: elsewhere kubectl may point at an unrelated cluster. Also
    skipped if the port is already serving (e.g. user ran their own
    port-forward) or if `kubectl` is missing.
    """
    if config.TARGET != "devbox":
        return
    if _port_open("127.0.0.1", 9000):
        logger.info("Storage port 9000 already open; skipping port-forward")
        return
    try:
        proc = subprocess.Popen(
            ["kubectl", "port-forward", "-n", "flyte", "svc/rustfs-svc", "9000:9000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.warning("kubectl not found; skipping storage port-forward")
        return
    atexit.register(proc.terminate)
    for _ in range(20):
        if _port_open("127.0.0.1", 9000):
            logger.info("Storage port-forward established on localhost:9000")
            return
        time.sleep(0.25)
    raise RuntimeError("kubectl port-forward did not open localhost:9000 within 5s")


def _port_open(host: str, port: int) -> bool:
    """Return True if a TCP connect to host:port succeeds quickly."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.25)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


def main():
    """Deploy the admin app to Flyte."""
    # A Union deploy with no workspace root looks healthy but can't save a
    # single notebook — refuse it rather than ship that.
    if config.TARGET == "union" and not config.WORKSPACE_ROOT:
        raise SystemExit(
            "STARGAZER_WORKSPACE_ROOT is not set. Export the object-store prefix "
            "users' notebooks are saved under (e.g. s3://<bucket>/stargazer) "
            "before deploying."
        )
    init(config.FLYTE_CONFIG, root_dir=PROJECT_ROOT)
    _start_storage_port_forward()
    # In-cluster init can't discover the org in an app pod; bake the deployer's.
    if org := get_init_config().org:
        app_env.env_vars["FLYTE_ORG"] = org
    app_env.env_vars["STARGAZER_NOTEBOOK_IMAGE"] = _build_notebook_image()
    deployment = flyte.serve(app_env)
    print(f"App URL: {deployment.endpoint}")


if __name__ == "__main__":
    main()
