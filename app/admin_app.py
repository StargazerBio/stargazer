"""
### Stargazer dashboard — one user's notebook home and launcher.

One deployment per user, in that user's own Flyte project (`u-<handle>`),
behind Union's login (`requires_auth=True`). The owner's subject is baked
into the env at deploy (`SG_OWNER_SUBJECT`) and the project is the one the
dashboard runs in (`FLYTE_PROJECT`); neither is derived from the request.
Union's login gates the public address, and on Union every request must also
carry its signed token, from the owner or a listed admin (`app.identity`),
since the in-cluster address skips the login. Whoever gets in sees the
owner's dashboard. There is no OAuth flow, session cookie, or GitHub
integration. It has three jobs:

1. **Dashboard.** Renders the notebook tile sections: Workflows and
   Tutorials (shipped in the per-notebook image), and Workspace (the owner's
   notebooks). The owner's notebooks live in the workspace store
   (`app.workspace_store`), keyed by their Union subject, so saving needs no
   setup. On Union its header links to the project's runs in the Union
   console (`config.CONSOLE_URL`).

2. **Workspace actions.** Create, setup, delete, copy and download, all
   against the workspace store. A notebook's tile name and description
   (`app.notebook_meta`) and its pod's environment (`main_env`,
   `app.notebook_environment`) are declared in its setup block, which the
   tile's gear edits.

3. **Launch broker.** `POST /launch` builds a per-notebook AppEnvironment via
   `app.per_notebook.per_notebook_env(...)` from the environment the
   notebook declares, owned by the same user, serves it into the
   dashboard's project, and returns its URL. Serving builds a declared image
   first. The dashboard never calls a notebook pod: the pod hydrates and
   saves its own workspace and shows its own starting page while it warms
   up.

The user's asset index isn't the dashboard's: it's their table on Aurora
DSQL (a Postgres server on the devbox), which the dashboard's asset browser
(`app.assets`), their notebook pods and the runs those start all reach
directly, at the URL the deploy bakes in (`STARGAZER_INDEX_URL`).

The asset manager (`app.assets`) reaches Pinata with the org's key, which the
dashboard gets as a Flyte secret: injected into the pod, never in the app
spec the owner can read.

`app_env` (this app's own AppEnvironment) is also defined here. It is
deployed per user by `app.deploy.deploy_dashboard`, which onboarding
(`stargazer-users`, in the infra repo) calls; never on its own.

Local development (identity comes from the `X-User-*` headers Union would set):
    SG_OWNER_SUBJECT=<subject> uvicorn app.admin_app:asgi_app --reload --port 8080

Deploy hosted to Flyte, one per user, from the infra repo:
    stargazer-users onboard --email … --first-name … --last-name …

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import flyte
import flyte.app
import flyte.errors
from fastapi import FastAPI, Form, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from flyte.remote import App

from app import config
from app import workspace_store as store
from app.assets import TUS_CHUNK_BYTES, TUS_MAX_BYTES, public_assets_on
from app.assets import router as assets_router
from app.identity import CurrentUser, User
from app.init import init
from app.notebook_environment import (
    MainEnvError,
    evaluate_main_env,
    extract_main_env,
    forget_new_environments,
)
from app.notebook_meta import (
    SetupError,
    notebook_description,
    notebook_name,
    replace_setup_body,
    setup_body,
    with_setup_values,
)
from app.notebooks import (
    SEED_SLUGS,
    Notebook,
    by_section,
    by_slug,
    seed_source,
    shipped_source,
    slugify,
)
from app.per_notebook import (
    NOTEBOOK_SLUG_MAX,
    WORKSPACE_NOTEBOOK_DIR,
    list_project_apps,
    per_notebook_env,
)
from app.templates import templates
from stargazer.config import (
    IMAGE_PLATFORM,
    PROJECT_ROOT,
    STARGAZER_ENV_VARS,
    STARGAZER_SECRETS,
    logger,
)

# ---------------------------------------------------------------------------
# Flyte AppEnvironment for the dashboard itself.
# ---------------------------------------------------------------------------

# The dashboard's own project: notebooks are served into it, and code-bundle
# uploads during `serve.aio(per_notebook_env)` use the client's init-time
# project (`with_servecontext(project=...)` alone is not enough).
_FLYTE_CONTEXT = {
    "FLYTE_PROJECT": config.FLYTE_PROJECT,
    "FLYTE_DOMAIN": config.FLYTE_DOMAIN,
}

# Non-secret config request handlers read at runtime, baked into the pod env so
# the deployed dashboard sees what the deployer's shell set. The workspace root
# must match what notebook pods hydrate from and save to.
_PUBLIC_CONFIG = {
    name: value
    for name, value in (
        ("STARGAZER_WORKSPACE_ROOT", config.WORKSPACE_ROOT),
        ("SG_OWNER_SUBJECT", config.OWNER_SUBJECT),
    )
    if value
}


app_env = flyte.app.AppEnvironment(
    name="dashboard",
    description="Stargazer dashboard and notebook launcher",
    image=(
        flyte.Image.from_debian_base(
            name="dashboard",
            registry=os.environ.get("STARGAZER_REGISTRY"),
            platform=IMAGE_PLATFORM,
        )
        .with_apt_packages("ca-certificates")
        .with_uv_project(
            PROJECT_ROOT / "pyproject.toml",
            project_install_mode="install_project",
            extra_args="--extra landing",
        )
        .with_commands(["flyte create config --local-persistence"])
    ),
    # `exec` so the shell `fserve` starts becomes uvicorn, the process
    # `fserve` signals at scale-to-zero (see `app.per_notebook`).
    args=[
        "exec",
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
    scaling=flyte.app.Scaling(replicas=(0, 1), scaledown_after=timedelta(hours=1)),
    env_vars={
        **STARGAZER_ENV_VARS,
        **_FLYTE_CONTEXT,
        **_PUBLIC_CONFIG,
    },
    # The Pinata key as a secret, never in `env_vars`: the owner can read the
    # app spec, and Union keeps only a reference to a secret there. The devbox
    # drops app secrets, so a devbox dashboard has no public tier.
    secrets=STARGAZER_SECRETS,
    # Flyte's loaded_modules bundler ships only the .py files the deployer
    # imported; HTML and the landing-page logo must be enumerated. The
    # bundle's `app/` shadows the installed package in the pod, so a missing
    # file can't be found.
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
    and a fresh 200 once a redeploy changes the file.
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


def _console_runs_url() -> str:
    """This dashboard's project's runs in the Union console, or "" with no console.

    The console's runs list for a project is
    `<console>/v2/domain/<domain>/project/<project>/runs`.
    """
    if not config.CONSOLE_URL:
        return ""
    return (
        f"{config.CONSOLE_URL}/v2/domain/{config.FLYTE_DOMAIN}"
        f"/project/{config.FLYTE_PROJECT}/runs"
    )


def _store_ready() -> bool:
    """Whether this deploy has a workspace store to save notebooks in."""
    return bool(config.WORKSPACE_ROOT)


def _store_off() -> JSONResponse:
    """The 503 every store-backed route returns without a store."""
    return JSONResponse({"error": _STORE_OFF}, status_code=503)


def _failed(action: str, exc: Exception) -> JSONResponse:
    """The 500 a route returns when the store or control plane fails it.

    Not a 502, though the failure is upstream: Cloudflare, in front of every
    Union app, replaces a 502's (or 504's) body with its own error page, so
    the reason would never reach the page. A 500's body passes through.
    """
    return JSONResponse({"error": f"{action} failed: {exc}"}, status_code=500)


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


def _tile_dict(slug: str, title: str, description: str, section: str) -> dict:
    """Build the context dict consumed by `_tile.html`."""
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "section": section,
    }


def _display_name(filename: str) -> str:
    """Human-friendly tile title for a notebook file.

    Drops the `.py` extension and capitalizes the first letter, so
    `my-notebook.py` tiles as `My-notebook`.
    """
    stem = filename.removesuffix(".py")
    return stem[:1].upper() + stem[1:]


_GENERIC_WS_DESC = "Personal workspace notebook."


def _workspace_tile_dict(slug: str, name: str, description: str) -> dict:
    """A workspace tile titled by the notebook's `main_name` and `main_description`.

    The name is preserved verbatim as the user typed it; without one the
    title falls back to a filename-derived form.
    """
    return _tile_dict(
        slug,
        name or _display_name(f"{slug}.py"),
        description or _GENERIC_WS_DESC,
        "workspace",
    )


async def _workspace_tiles(user: User) -> list[dict]:
    """Build Workspace tiles from the user's own notebooks in the store.

    Each notebook's setup block is read (in parallel, best-effort) for its
    tile's name and description. A failed read falls back to the
    filename-derived title and the generic blurb rather than dropping the tile.
    """
    try:
        files = await store.list_workspace(user.subject)
    except Exception as exc:
        logger.warning(f"Workspace listing failed for {user.subject!r}: {exc}")
        return []
    slugs = [s for f in files if (s := f.removesuffix(".py")) not in SEED_SLUGS]

    async def _tile(slug: str) -> dict:
        """Build one workspace tile from its setup block (best-effort)."""
        name, desc = "", ""
        try:
            src = await store.get_workspace_notebook(user.subject, f"{slug}.py")
            if src:
                name, desc = notebook_name(src), notebook_description(src)
        except Exception as exc:
            logger.warning(f"Workspace metadata read failed for {slug!r}: {exc}")
        return _workspace_tile_dict(slug, name, desc)

    return list(await asyncio.gather(*[_tile(s) for s in slugs]))


async def _teardown_notebook_pods(user: User, slug: str) -> None:
    """Completely tear down each edit/run pod for a notebook slug.

    Deactivate first (a clean stop), then delete the deployment record, so the
    notebook leaves nothing behind — no tile to Stop it, no orphan for
    `/workspace/cleanup` to reap. Shared by every route that removes a
    notebook from the dashboard. Every step is best-effort and never raises.
    """
    project = config.FLYTE_PROJECT
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
    """Render the owner's dashboard: their notebooks, then the asset browser."""
    workspace = await _workspace_tiles(user) if _store_ready() else []
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Dashboard",
            "user": user,
            "workspace_configured": _store_ready(),
            "tutorials": [
                _tile_dict(n.slug, n.title, n.description, "tutorials")
                for n in by_section("tutorials")
            ],
            "workflows": [
                _tile_dict(n.slug, n.title, n.description, "workflows")
                for n in by_section("workflows")
            ],
            "workspace": workspace,
            "settings": await _settings(user),
            "version": config.VERSION,
            "console_runs_url": _console_runs_url(),
            # The asset browser compares `_owner` against the visitor.
            "username": user.subject,
            "pinata_configured": public_assets_on(),
            "tus_max_bytes": TUS_MAX_BYTES,
            "tus_chunk_bytes": TUS_CHUNK_BYTES,
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
):
    """Create a new workspace notebook from the blank or template seed.

    Writes `<slug>.py` to the user's store with the name the user typed as
    its `main_name`, then returns the rendered tile. The seed's own setup
    block declares the pod's resources, which the tile's gear edits
    afterward (`/workspace/setup`) along with the description. Create stays
    a pure "add a notebook" action: no launch, no navigation. A name whose
    slug is over `NOTEBOOK_SLUG_MAX` is refused, since its app could never be
    deployed.
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
    if len(slug) > NOTEBOOK_SLUG_MAX:
        return JSONResponse(
            {"error": f"Notebook names can be at most {NOTEBOOK_SLUG_MAX} characters."},
            status_code=400,
        )

    # The title the user typed, preserved verbatim (whitespace collapsed) for
    # the tile; the slug above is the lowercased, dash-joined filename form.
    display_name = " ".join(name.split())
    filename = f"{slug}.py"
    seed = seed_source(source)
    if seed is None:
        return JSONResponse({"error": f"{source} seed not found"}, status_code=500)
    content = with_setup_values(seed, main_name=display_name)
    try:
        await store.create_workspace_notebook(user.subject, filename, content)
    except store.NotebookExistsError:
        return JSONResponse(
            {"error": f"notebook already exists: {filename}"}, status_code=409
        )
    except Exception as exc:
        logger.error(f"Notebook create failed for {filename!r}: {exc}")
        return _failed("create", exc)

    tile = _workspace_tile_dict(slug, display_name, notebook_description(content))
    return JSONResponse({"slug": slug, "tile_html": _render_tile(tile)})


def _copy_source(slug: str, section: str) -> tuple[str, str, str]:
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
    raise ValueError(f"cannot copy from section: {section}")


@asgi_app.post("/workspace/copy")
async def workspace_copy(
    user: CurrentUser, slug: str = Form(...), section: str = Form(...)
):
    """Copy a Workflows notebook into the user's workspace.

    The source is a shipped Workflows notebook; it's written as a fresh,
    editable workspace notebook. The copy keeps the source's setup block, and
    the workflow's title and blurb are declared in it as `main_name` and
    `main_description`, so it tiles like any other workspace notebook. The target slug is derived from the source title;
    like `/workspace/create` it fails with 409 if that name is taken. Returns
    the rendered Workspace tile.
    """
    if not _store_ready():
        return _store_off()
    try:
        source, title, desc = _copy_source(slug, section)
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
    content = with_setup_values(source, main_name=title, main_description=desc)
    try:
        await store.create_workspace_notebook(user.subject, filename, content)
    except store.NotebookExistsError:
        return JSONResponse(
            {"error": f"notebook already exists: {filename}"}, status_code=409
        )
    except Exception as exc:
        logger.error(f"Notebook copy failed for {slug!r} from {section}: {exc}")
        return _failed("copy", exc)

    tile = _workspace_tile_dict(target_slug, title, desc)
    return JSONResponse({"slug": target_slug, "tile_html": _render_tile(tile)})


# Shown in the gear's editor for a notebook that has no setup block yet.
_STARTER_SETUP = (
    "import flyte\n"
    "\n"
    "from stargazer.notebooks import notebook_env\n"
    "\n"
    'main_description = ""\n'
    "main_env = notebook_env.clone_with(\n"
    '    name="notebook", resources=flyte.Resources(cpu=2, memory="4Gi")\n'
    ")\n"
)


@asgi_app.get("/workspace/setup")
async def workspace_setup(user: CurrentUser, slug: str):
    """Return a workspace notebook's setup block body, for the gear's editor.

    The body comes without its `with app.setup:` line and flush left. A
    notebook without a setup block gets a starter body to save.
    """
    if not _store_ready():
        return _store_off()
    if bad := _invalid_slug(slug):
        return bad
    source = await store.get_workspace_notebook(user.subject, f"{slug}.py")
    if source is None:
        return JSONResponse({"error": "notebook not found"}, status_code=404)
    return JSONResponse({"slug": slug, "setup": setup_body(source) or _STARTER_SETUP})


@asgi_app.post("/workspace/setup")
async def workspace_setup_save(
    user: CurrentUser, slug: str = Form(...), setup: str = Form(...)
):
    """Replace a workspace notebook's setup block body with the gear editor's.

    The body is indented back under the block's own `with app.setup:` line.
    A body that won't parse, declares a name or description the dashboard
    can't read, or a `main_env` it can't serve, is a 400 with the reason, and
    nothing is written. Environment changes take effect at the **next**
    `/launch`; the tile's name and description, which this returns, change
    right away.
    """
    if not _store_ready():
        return _store_off()
    if bad := _invalid_slug(slug):
        return bad
    filename = f"{slug}.py"
    try:
        source = await store.get_workspace_notebook(user.subject, filename)
        if source is None:
            return JSONResponse(
                {"error": f"notebook not found: {filename}"}, status_code=404
            )
        try:
            content = replace_setup_body(source, setup)
            if (expr := extract_main_env(content)) is not None:
                with forget_new_environments():
                    evaluate_main_env(expr)
        except (SetupError, MainEnvError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        await store.update_workspace_notebook(user.subject, filename, content)
    except Exception as exc:
        logger.error(f"Notebook setup update failed for {filename!r}: {exc}")
        return _failed("update", exc)

    tile = _workspace_tile_dict(
        slug, notebook_name(content), notebook_description(content)
    )
    return JSONResponse(
        {"slug": slug, "title": tile["title"], "description": tile["description"]}
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
        return _failed("delete", exc)
    return JSONResponse({"status": "deleted", "slug": slug})


@asgi_app.get("/workspace/download")
async def workspace_download(user: CurrentUser, slug: str):
    """Download a workspace notebook's `.py` source as an attachment.

    This is the path for sharing a notebook upstream: download it and
    contribute it like any file.
    """
    if not _store_ready():
        return _store_off()
    if bad := _invalid_slug(slug):
        return bad
    filename = f"{slug}.py"
    source = await store.get_workspace_notebook(user.subject, filename)
    if source is None:
        return JSONResponse({"error": "notebook not found"}, status_code=404)
    return Response(
        source,
        media_type="text/x-python; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


async def _settings(user: User) -> dict:
    """The user's settings, or the defaults when the store can't say."""
    if not _store_ready():
        return dict(store.DEFAULT_SETTINGS)
    try:
        return await store.get_settings(user.subject)
    except Exception as exc:
        logger.warning(f"Settings read failed for {user.subject}: {exc}")
        return dict(store.DEFAULT_SETTINGS)


@asgi_app.post("/settings")
async def save_settings(user: CurrentUser, save_interval_seconds: str = Form("")):
    """Save the user's settings; notebooks started afterwards use them.

    The save interval is a whole number of seconds, 0 or more. Anything else
    is a 400, and nothing is stored. Returns the settings as saved.
    """
    if not _store_ready():
        return _store_off()
    text = save_interval_seconds.strip()
    if not (text.isascii() and text.isdigit()):
        return JSONResponse(
            {"error": "The save interval is a whole number of seconds, 0 or more."},
            status_code=400,
        )
    try:
        settings = await store.get_settings(user.subject)
        settings["save_interval_seconds"] = int(text)
        await store.put_settings(user.subject, settings)
    except Exception as exc:
        logger.error(f"Settings save failed for {user.subject}: {exc}")
        return _failed("settings save", exc)
    return JSONResponse(settings)


# ---------------------------------------------------------------------------
# Launch / stop / status / cleanup
# ---------------------------------------------------------------------------

_SECTIONS = ("tutorials", "workflows", "workspace")


async def _launch_target(
    user: User, slug: str, section: str
) -> tuple[str, str | None] | None:
    """Resolve a launch to `(notebook_path, source)`, or None if unknown.

    `source` is a workspace notebook's, whose setup block can declare its
    pod's environment. It's None for tutorials and workflows, which run in
    `notebook_env`, and for a workspace notebook that can't be read.
    """
    if section == "workspace":
        path = f"{WORKSPACE_NOTEBOOK_DIR}/{slug}.py"
        try:
            source = await store.get_workspace_notebook(user.subject, f"{slug}.py")
        except Exception as exc:
            logger.warning(f"Setup read failed for {slug!r}: {exc}")
            source = None
        return path, source
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
    """Spawn (or reuse) the owner's per-notebook app for slug+mode; return its URL.

    The pod is served into the dashboard's project and owned by the same
    user, hydrates and saves its own workspace, and shows a starting page
    until the notebook is ready, so the URL is returned as soon as the app is
    admitted.

    The pod runs in the environment the notebook declares (`main_env`), with
    the dashboard's fields on top. `serve` builds a declared image first when
    it isn't built yet, so the first launch after a change waits for the
    build. An environment that won't evaluate, or an image that won't build,
    is a 422 with the reason, never a pod sized or built wrong.
    """
    if mode not in ("edit", "run"):
        return JSONResponse({"error": f"invalid mode: {mode}"}, status_code=400)
    if section not in _SECTIONS:
        return JSONResponse({"error": f"invalid section: {section}"}, status_code=400)
    if section == "workspace":
        if not _store_ready():
            return _store_off()
        if bad := _invalid_slug(slug):
            return bad

    target = await _launch_target(user, slug, section)
    if target is None:
        return JSONResponse({"error": f"unknown notebook: {slug}"}, status_code=404)
    notebook_path, source = target
    with forget_new_environments():
        return await _serve_notebook(request, user, slug, mode, notebook_path, source)


async def _serve_notebook(
    request: Request,
    user: User,
    slug: str,
    mode: str,
    notebook_path: str,
    source: str | None,
) -> JSONResponse:
    """Evaluate the notebook's `main_env`, serve its pod, and answer `/launch`."""
    declared = None
    if source and (expr := extract_main_env(source)) is not None:
        try:
            declared = evaluate_main_env(expr)
        except MainEnvError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)

    project = config.FLYTE_PROJECT
    env = per_notebook_env(
        slug=slug,
        mode=mode,
        notebook_path=notebook_path,
        owner_subject=user.subject,
        admin_url=str(request.base_url).rstrip("/"),
        index_url=os.environ["STARGAZER_INDEX_URL"],
        declared=declared,
    )
    env.env_vars["FLYTE_PROJECT"] = project
    # App pods aren't given the org (task pods get `_U_ORG_NAME`); pass ours on
    # so in-pod SDK calls address the tenant's org.
    if os.environ.get("FLYTE_ORG"):
        env.env_vars["FLYTE_ORG"] = os.environ["FLYTE_ORG"]
    # Owner attribution: workspace MCP/SDK uploads stamp `_owner` from this
    # (and config.py forwards it onward into task pods at run submission).
    env.env_vars["STARGAZER_OWNER"] = user.subject
    # Read at launch: a running pod keeps the interval it started with.
    env.env_vars["SG_SAVE_INTERVAL_SECONDS"] = str(
        (await _settings(user))["save_interval_seconds"]
    )

    # `serve.aio()` watches the deployment to readiness and raises if the pod
    # is slow to schedule/boot. That's not a real failure: the route (and
    # `App.endpoint`) exist as soon as the app is admitted, and the pod shows
    # its own starting page. So on a watch error, recover the endpoint and
    # hand it back anyway. An app that isn't there was refused outright, and
    # retrying won't change that, so the serve error goes back as the reason (a
    # 422, since Cloudflare in front of Union apps replaces a 502's body).
    try:
        deployment = await flyte.with_servecontext(
            project=project, domain=config.FLYTE_DOMAIN
        ).serve.aio(env)
        endpoint = deployment.endpoint
    except flyte.errors.ImageBuildError as exc:
        # Before the watch recovery below, which would hand back the app as it
        # was last served: on its old image.
        logger.error(f"main_env image build failed for {slug!r}: {exc}")
        return JSONResponse(
            {"error": f"This notebook's image failed to build: {exc}"},
            status_code=422,
        )
    except Exception as exc:
        logger.warning(f"serve watch unconfirmed for {slug!r}/{mode!r}: {exc}")
        try:
            app = await App.get.aio(
                name=f"nb-{slug}-{mode}", project=project, domain=config.FLYTE_DOMAIN
            )
        except Exception:
            return JSONResponse({"error": str(exc)}, status_code=422)
        endpoint = app.endpoint
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
    project = config.FLYTE_PROJECT
    name = f"nb-{slug}-{mode}"
    try:
        app = await App.get.aio(name=name, project=project, domain=config.FLYTE_DOMAIN)
        await app.deactivate.aio()
    except Exception as exc:
        logger.error(f"Stop failed for {name!r} in {project!r}: {exc}")
        return _failed("stop", exc)
    return JSONResponse({"stopped": True})


@asgi_app.get("/launch/status")
async def launch_status(user: CurrentUser):
    """Report which of the user's notebooks have an active per-notebook app.

    Discovery is one control-plane list (`list_project_apps`, the same call
    `/workspace/cleanup` uses) of every deployment in the user's project,
    filtered to `nb-{slug}-{mode}` names. Each is then re-fetched with
    `App.get` (in parallel) for authoritative status, since a list payload may
    not carry full conditions, and the active ones are returned with their
    endpoints. Read live from the control plane, so it survives dashboard
    restarts. The dashboard calls this on load to render running notebooks
    straight to Open+Stop.
    """
    project = config.FLYTE_PROJECT
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
    project = config.FLYTE_PROJECT
    try:
        apps = await list_project_apps(project, domain=config.FLYTE_DOMAIN)
    except Exception as exc:
        logger.error(f"cleanup listing failed for {project!r}: {exc}")
        return _failed("cleanup", exc)

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
