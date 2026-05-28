"""
### Stargazer admin app — OAuth, provisioning, and the dashboard itself.

Shared, single deployment. Handles three roles in one FastAPI service:

1. **Unauthenticated landing + GitHub OAuth.** Users sign in with GitHub;
   the callback forks the upstream stargazer repo into their account,
   ensures their Flyte project exists, then drops them onto the
   dashboard.

2. **Per-user dashboard.** Renders three sections of notebook tiles —
   Tutorials, Community (both shipped in the per-notebook image),
   Workspace (lives in the user's GitHub fork and is listed either via
   a running per-notebook pod's local clone or, as a cold-case fallback,
   via the GitHub Contents API).

3. **Launch broker.** `POST /launch?slug=…&mode=…` builds a per-notebook
   AppEnvironment via `app.per_notebook.per_notebook_env(...)`, serves
   it into the user's Flyte project, and redirects the browser to the
   resulting URL.

`app_env` (this app's own AppEnvironment) and `main()` (the deploy
entrypoint) are also defined here.

Local development:
    uvicorn app.admin_app:asgi_app --reload --port 8080

Deploy hosted to Flyte:
    python -m app.admin_app           # or: stargazer-app

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import atexit
import os
import secrets
import socket
import subprocess
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

import flyte
import flyte.app
import httpx
from flyte.remote import App
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from stargazer.config import (
    PROJECT_ROOT,
    STARGAZER_ENV_VARS,
    logger,
)

from app.github import fork_upstream, list_workspace as gh_list_workspace
from app.init import init
from app.notebooks import WORKSPACE_NOTEBOOK_DIR, Notebook, by_section, by_slug
from app.oauth import exchange_code, get_github_user, github_auth_url
from app.per_notebook import (
    NOTEBOOK_IMAGE_URI,
    notebook_app_img_recipe,
    per_notebook_env,
)
from app.provision import provision_user, sanitize_project_id
from app.session import (
    SESSION_COOKIE,
    SessionData,
    create_session_cookie,
    session_from_request,
)
from app.templates import templates


# ---------------------------------------------------------------------------
# Flyte AppEnvironment for the admin app itself.
# ---------------------------------------------------------------------------

# Devbox secret-injection workaround: AppEnvironment `secrets=[...]` is a
# no-op on App pods (no `inject-flyte-secrets` label). Bake OAuth secrets
# from the deployer's local shell into `env_vars`. Export them before
# `python -m app.admin_app`.
# See .opencode/reference/devbox_workarounds.md
_SECRET_NAMES = ("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "SESSION_SECRET")
_RUNTIME_SECRETS = {
    name: os.environ[name] for name in _SECRET_NAMES if os.environ.get(name)
}

# Admin pod needs a default Flyte project for code-bundle uploads during
# per-user `serve.aio(per_notebook_env)` calls. `with_servecontext(project=...)`
# alone is not enough — the upload uses the client's init-time project.
_FLYTE_CONTEXT = {
    "FLYTE_PROJECT": os.environ.get("FLYTE_PROJECT", "flytesnacks"),
    "FLYTE_DOMAIN": os.environ.get("FLYTE_DOMAIN", "development"),
}


app_env = flyte.app.AppEnvironment(
    name="admin-app",
    description="Stargazer landing, OAuth, dashboard, and notebook launcher",
    image=(
        flyte.Image.from_debian_base(
            name="admin-app",
            registry=os.environ["STARGAZER_REGISTRY"],
            platform=("linux/amd64", "linux/arm64"),
        )
        .with_apt_packages("ca-certificates", "git")
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
    requires_auth=False,
    resources=flyte.Resources(memory=("512Mi", "1Gi")),
    env_vars={**STARGAZER_ENV_VARS, **_RUNTIME_SECRETS, **_FLYTE_CONTEXT},
    # Flyte's loaded_modules bundler ships only .py files; HTML and the
    # landing-page logo must be enumerated.
    include=("templates/", "static/"),
)


# ---------------------------------------------------------------------------
# Per-user launched-pod registry (in-memory; volatile across admin restarts)
# ---------------------------------------------------------------------------


# `_launched[github_username][(slug, mode)]` is the public endpoint URL of
# every per-notebook pod the user has spawned at least once. Used by:
#   - `/launch/status` to probe `<endpoint>/__sg__/ready` for the dashboard
#     spinner (the in-cluster `.svc.cluster.local` DNS pattern was unreliable
#     across cluster configs; going through the same URL the browser uses
#     sidesteps the question entirely).
#   - `/__sg__/workspace/list` queries when rendering the dashboard.
# In-memory only — admin restarts clear it; users would then re-click Edit/Run
# to repopulate.
_launched: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


def _env(key: str) -> str:
    """Read a required environment variable."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Missing required env var: {key}")
    return value


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize Flyte client so /launch can call flyte.serve.aio()."""
    init()
    yield


asgi_app = FastAPI(title="Stargazer", docs_url=None, redoc_url=None, lifespan=lifespan)
asgi_app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)


def _redirect_uri(request: Request) -> str:
    """Build the OAuth callback URI."""
    base = os.environ.get("LANDING_BASE_URL")
    if base:
        return f"{base.rstrip('/')}/auth/callback"
    return str(request.url_for("auth_callback"))


def _get_session(request: Request) -> SessionData | None:
    """Extract a valid session from the request cookie, if present."""
    return session_from_request(request, _env("SESSION_SECRET"))


# ---------------------------------------------------------------------------
# Workspace listing helper
# ---------------------------------------------------------------------------


async def _list_workspace_from_pods(
    session_cookie: str, endpoints: dict[tuple[str, str], str]
) -> list[str] | None:
    """Try each previously-launched per-notebook pod for a workspace listing.

    Returns the first successful response's file list, or None if no pod
    answers within the short per-attempt timeout. Uses each pod's public
    endpoint URL (cached at /launch time) so the request follows the same
    path the browser uses — no dependence on in-cluster DNS.
    """
    for endpoint in endpoints.values():
        url = f"{endpoint.rstrip('/')}/__sg__/workspace/list"
        try:
            async with httpx.AsyncClient(
                timeout=2.0, follow_redirects=True
            ) as client:
                resp = await client.get(url, cookies={SESSION_COOKIE: session_cookie})
            if resp.status_code == 200:
                return resp.json().get("files", [])
        except Exception:
            continue
    return None


async def _resolve_workspace_files(
    session: SessionData, cookie_value: str
) -> list[str]:
    """Return the user's workspace files, preferring a live pod over GitHub."""
    known = _launched.get(session.github_username, {})
    from_pod = await _list_workspace_from_pods(cookie_value, known)
    if from_pod is not None:
        return from_pod
    if not session.access_token or not session.fork_owner:
        return []
    try:
        return await gh_list_workspace(session.fork_owner, session.access_token)
    except Exception as exc:
        logger.warning(f"GitHub workspace listing failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Routes — login / dashboard / launch
# ---------------------------------------------------------------------------


def _tile_dict(slug: str, title: str, description: str, section: str) -> dict:
    """Build the context dict consumed by `_tile.html`."""
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "section": section,
    }


def _dashboard_context(github_username: str, workspace_files: list[str]) -> dict:
    """Assemble the tile lists Jinja's `dashboard.html` iterates over."""
    return {
        "title": "Dashboard",
        "github_username": github_username,
        "tutorials": [
            _tile_dict(n.slug, n.title, n.description, "tutorials")
            for n in by_section("tutorials")
        ],
        "community": [
            _tile_dict(n.slug, n.title, n.description, "community")
            for n in by_section("community")
        ],
        "workspace": [
            _tile_dict(
                slug=f.removesuffix(".py"),
                title=f,
                description="Personal workspace notebook.",
                section="workspace",
            )
            for f in workspace_files
        ],
    }


@asgi_app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Render the login page or the dashboard depending on session state."""
    session = _get_session(request)
    if not session:
        return templates.TemplateResponse(
            request, "login.html", {"title": "Sign In"}
        )
    cookie_value = request.cookies.get(SESSION_COOKIE, "")
    files = await _resolve_workspace_files(session, cookie_value)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _dashboard_context(session.github_username, files),
    )


@asgi_app.get("/auth/login")
async def auth_login(request: Request):
    """Redirect to GitHub for OAuth authorization."""
    state = secrets.token_urlsafe(32)
    url = github_auth_url(
        client_id=_env("GITHUB_CLIENT_ID"),
        redirect_uri=_redirect_uri(request),
        state=state,
    )
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "oauth_state",
        state,
        httponly=True,
        secure=False,
        max_age=600,
        samesite="lax",
    )
    return response


@asgi_app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request, code: str, state: str):
    """Handle GitHub OAuth callback, then provision the user."""
    expected_state = request.cookies.get("oauth_state")
    if not expected_state or not secrets.compare_digest(state, expected_state):
        return RedirectResponse("/", status_code=302)

    access_token = await exchange_code(
        client_id=_env("GITHUB_CLIENT_ID"),
        client_secret=_env("GITHUB_CLIENT_SECRET"),
        code=code,
        redirect_uri=_redirect_uri(request),
    )
    github_user = await get_github_user(access_token)
    username = github_user["login"]

    try:
        fork = await fork_upstream(access_token)
        fork_owner = fork["owner"]["login"]
    except Exception as exc:
        logger.error(f"Fork creation failed for {username!r}: {exc}")
        fork_owner = username  # best-effort assumption

    try:
        await provision_user(github_username=username)
    except Exception as exc:
        logger.error(f"Provisioning failed for {username!r}: {exc}")

    session = SessionData(
        github_username=username,
        github_id=github_user["id"],
        fork_owner=fork_owner,
        access_token=access_token,
    )
    cookie = create_session_cookie(session, _env("SESSION_SECRET"))
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        cookie,
        httponly=True,
        secure=False,
        max_age=60 * 60 * 24 * 30,
        samesite="lax",
    )
    response.delete_cookie("oauth_state")
    return response


@asgi_app.get("/auth/logout")
async def auth_logout():
    """Clear session and redirect to landing page."""
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


@asgi_app.post("/launch")
async def launch(
    request: Request,
    slug: str = Form(...),
    mode: str = Form(...),
    section: str = Form(...),
):
    """Spawn (or reuse) a per-notebook app for the requested slug+mode."""
    # AJAX callers parse the response as JSON; a 302 to /login would be
    # silently followed by fetch() and decoded as HTML, breaking JSON.parse.
    wants_json = "application/json" in request.headers.get("accept", "")

    def _reject(message: str, status: int):
        if wants_json:
            return JSONResponse({"error": message}, status_code=status)
        return RedirectResponse("/", status_code=302)

    session = _get_session(request)
    if session is None:
        return _reject("not authenticated", 401)
    if mode not in ("edit", "run"):
        return _reject(f"invalid mode: {mode}", 400)
    if section not in ("tutorials", "community", "workspace"):
        return _reject(f"invalid section: {section}", 400)

    if section == "workspace":
        notebook_path = f"{WORKSPACE_NOTEBOOK_DIR}/{slug}.py"
    else:
        nb: Notebook | None = by_slug(slug)
        if nb is None or nb.section != section:
            return _reject(f"unknown notebook: {slug}", 404)
        notebook_path = nb.path_in_image

    project = sanitize_project_id(session.github_username)
    # Prefer the explicit LANDING_BASE_URL (set in hosted deploys); fall back
    # to the request's own base_url so local dev (`uvicorn ... --reload`) works
    # without extra config.
    admin_url = (
        os.environ.get("LANDING_BASE_URL") or str(request.base_url)
    ).rstrip("/")
    env = per_notebook_env(
        slug=slug,
        mode=mode,  # type: ignore[arg-type]
        notebook_path=notebook_path,
        fork_owner=session.fork_owner,
        github_token=session.access_token,
        session_secret=_env("SESSION_SECRET"),
        admin_url=admin_url,
    )
    env.env_vars["FLYTE_PROJECT"] = project

    deployment = await flyte.with_servecontext(
        project=project, domain="development"
    ).serve.aio(env)
    _launched[session.github_username][(slug, mode)] = deployment.endpoint

    # Hand off the signed session as a one-shot query param. The admin and the
    # per-notebook live on sibling subdomains; browsers won't share the
    # admin's host-only cookie with the per-notebook host, and `Domain=` on
    # a bare TLD-like parent (`localhost`) is unreliable across browsers. The
    # proxy validates `sg_launch` on first hit, sets its own host-only
    # cookie, and 302s back to the clean URL.
    launch_token = request.cookies.get(SESSION_COOKIE, "")
    handoff = f"{deployment.endpoint}?sg_launch={launch_token}"

    # AJAX clients get the URL as JSON immediately so the dashboard tile can
    # start polling `/launch/status` for readiness and swap the spinner for
    # an "Open" link once the pod responds. Plain form submissions (no JS)
    # still get the 303 redirect.
    if wants_json:
        return JSONResponse({"url": handoff})
    return RedirectResponse(handoff, status_code=303)


@asgi_app.post("/stop")
async def stop(
    request: Request,
    slug: str = Form(...),
    mode: str = Form(...),
):
    """Deactivate the per-notebook app for the requested slug+mode."""
    session = _get_session(request)
    if session is None:
        return JSONResponse({"error": "not authenticated"}, status_code=401)
    if mode not in ("edit", "run"):
        return JSONResponse({"error": f"invalid mode: {mode}"}, status_code=400)

    project = sanitize_project_id(session.github_username)
    name = f"nb-{slug}-{mode}"
    try:
        app = await App.get.aio(name=name, project=project, domain="development")
        await app.deactivate.aio()
    except Exception as exc:
        logger.error(f"Stop failed for {name!r} in {project!r}: {exc}")
        return JSONResponse({"error": f"stop failed: {exc}"}, status_code=502)

    _launched.get(session.github_username, {}).pop((slug, mode), None)
    return JSONResponse({"stopped": True})


@asgi_app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Deploy entrypoint
# ---------------------------------------------------------------------------


def _build_and_push_notebook_image() -> None:
    """Build the per-notebook recipe and publish it under a stable tag.

    The admin pod cannot build images itself, so the deployer's machine
    must publish `notebook-app` to `STARGAZER_REGISTRY` before any
    user's `/launch` click can spawn a per-notebook app — the
    AppEnvironment image reference resolves at pod-pull time, not at
    deploy time.

    `flyte.build` produces a content-hashed URI; we then retag that
    manifest as `NOTEBOOK_IMAGE_URI` (`.../notebook-app:stable`) via
    `docker buildx imagetools create` so the multi-arch manifest is
    preserved without re-pulling. Per-notebook AppEnvironments reference
    the stable tag (`Image.from_base(NOTEBOOK_IMAGE_URI)`) so the admin
    pod never needs to recompute the content hash from in-pod Python
    state.
    """
    logger.info("Building per-notebook flyte.Image (recipe)")
    result = flyte.build(notebook_app_img_recipe)
    if result.uri is None:
        raise RuntimeError("flyte.build did not return an image URI")
    logger.info(f"Retagging {result.uri} as {NOTEBOOK_IMAGE_URI}")
    subprocess.run(
        [
            "docker",
            "buildx",
            "imagetools",
            "create",
            "-t",
            NOTEBOOK_IMAGE_URI,
            result.uri,
        ],
        check=True,
    )
    logger.info(f"Per-notebook image published at {NOTEBOOK_IMAGE_URI}")


def _start_storage_port_forward() -> None:
    """Open `localhost:9000 → svc/rustfs-svc:9000` for devbox deploys.

    `flyte-binary` returns signed upload URLs with host `rustfs-svc.flyte:9000`
    (so admin App pods can reach storage via k8s DNS, matching production
    behaviour). On the deployer's laptop that hostname only works if it
    resolves to `127.0.0.1` (NAS DNS or `/etc/hosts`) AND there's a
    port-forward to the in-cluster service.

    Skip silently if the port is already serving (e.g. user ran their
    own port-forward) or if `kubectl` is missing (production deploy).
    """
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
    """Deploy the admin landing app to Flyte."""
    missing = [name for name in _SECRET_NAMES if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            f"Missing required env vars: {', '.join(missing)}. "
            f"Export them before deploying."
        )
    init(root_dir=PROJECT_ROOT)
    _start_storage_port_forward()
    _build_and_push_notebook_image()
    deployment = flyte.serve(app_env)
    print(f"App URL: {deployment.endpoint}")


if __name__ == "__main__":
    main()
