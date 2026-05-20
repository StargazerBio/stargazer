"""
### Stargazer admin app — OAuth, provisioning, and the dashboard itself.

Shared, single deployment. Handles three roles in one FastAPI service:

1. **Unauthenticated landing + GitHub OAuth.** Users sign in with GitHub;
   the callback forks the upstream stargazer repo into their account,
   ensures their Flyte project + workspace PVC exist, then drops them
   onto the dashboard.

2. **Per-user dashboard.** Renders three sections of notebook tiles —
   Tutorials, Community (both shipped in the per-notebook image),
   Workspace (lives on the user's per-user PVC and is listed either via
   a running per-notebook pod or, as a cold-case fallback, via the
   GitHub Contents API).

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

import flyte
import flyte.app
import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from stargazer.config import (
    PROJECT_ROOT,
    STARGAZER_ENV_VARS,
    logger,
)

from app.github import fork_upstream, list_workspace as gh_list_workspace
from app.init import init
from app.notebooks import WORKSPACE_NOTEBOOK_DIR, Notebook, by_section, by_slug
from app.oauth import exchange_code, get_github_user, github_auth_url
from app.per_notebook import per_notebook_env
from app.provision import provision_user, sanitize_project_id
from app.session import (
    SESSION_COOKIE,
    SessionData,
    create_session_cookie,
    session_from_request,
)
from app.templates import dashboard_html, login_html


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
    # Flyte's loaded_modules bundler ships only .py files; HTML must be enumerated.
    include=("templates/",),
)


# ---------------------------------------------------------------------------
# Per-user launched-pod registry (in-memory; volatile across admin restarts)
# ---------------------------------------------------------------------------


# `_launched[github_username]` is the set of (slug, mode) the user has
# spawned at least once. Used to know which per-notebook pod's
# `/__sg__/workspace/list` to query when rendering the dashboard.
_launched: dict[str, set[tuple[str, str]]] = defaultdict(set)


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
    session_cookie: str, project: str, slug_modes: set[tuple[str, str]]
) -> list[str] | None:
    """Try each previously-launched per-notebook pod for a workspace listing.

    Returns the first successful response's file list, or None if no pod
    answers within the short per-attempt timeout. Cross-namespace HTTP
    inside the cluster uses Knative's deterministic DNS:
    `nb-<slug>-<mode>.<project>.svc.cluster.local`.
    """
    for slug, mode in slug_modes:
        url = (
            f"http://nb-{slug}-{mode}.{project}.svc.cluster.local/__sg__/workspace/list"
        )
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
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
    project = sanitize_project_id(session.github_username)
    known = _launched.get(session.github_username, set())
    from_pod = await _list_workspace_from_pods(cookie_value, project, known)
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


def _render_tiles(workspace_files: list[str]) -> str:
    """Compose the three-section tile grid HTML for the dashboard body."""

    def tile(slug: str, title: str, description: str, section: str) -> str:
        """Render one notebook tile with Edit / Run POST buttons."""
        return f"""
        <div class="tile">
          <h3>{title}</h3>
          <p>{description}</p>
          <form method="post" action="/launch" style="display:inline;">
            <input type="hidden" name="slug" value="{slug}">
            <input type="hidden" name="section" value="{section}">
            <input type="hidden" name="mode" value="edit">
            <button class="btn btn-notebook" type="submit">Edit</button>
          </form>
          <form method="post" action="/launch" style="display:inline;">
            <input type="hidden" name="slug" value="{slug}">
            <input type="hidden" name="section" value="{section}">
            <input type="hidden" name="mode" value="run">
            <button class="btn btn-github" type="submit">Run</button>
          </form>
        </div>
        """

    tutorials = "".join(
        tile(n.slug, n.title, n.description, "tutorials")
        for n in by_section("tutorials")
    )
    community = "".join(
        tile(n.slug, n.title, n.description, "community")
        for n in by_section("community")
    )
    workspace = "".join(
        tile(f.removesuffix(".py"), f, "Personal workspace notebook.", "workspace")
        for f in workspace_files
    ) or (
        '<p class="empty">No workspace notebooks yet. Once you Edit one, '
        "it'll land in <code>notebooks/workspace/</code> in your fork.</p>"
    )

    return f"""
    <section><h2>Tutorials</h2><div class="grid">{tutorials}</div></section>
    <section><h2>Community</h2><div class="grid">{community}</div></section>
    <section><h2>Workspace</h2><div class="grid">{workspace}</div></section>
    <div class="logout"><a href="/auth/logout">Sign out</a></div>
    """


@asgi_app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Render the login page or the dashboard depending on session state."""
    session = _get_session(request)
    if not session:
        return HTMLResponse(login_html())
    cookie_value = request.cookies.get(SESSION_COOKIE, "")
    files = await _resolve_workspace_files(session, cookie_value)
    return HTMLResponse(dashboard_html(session.github_username, _render_tiles(files)))


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
    session = _get_session(request)
    if session is None:
        return RedirectResponse("/", status_code=302)
    if mode not in ("edit", "run"):
        return RedirectResponse("/", status_code=302)
    if section not in ("tutorials", "community", "workspace"):
        return RedirectResponse("/", status_code=302)

    if section == "workspace":
        notebook_path = f"{WORKSPACE_NOTEBOOK_DIR}/{slug}.py"
    else:
        nb: Notebook | None = by_slug(slug)
        if nb is None or nb.section != section:
            return RedirectResponse("/", status_code=302)
        notebook_path = nb.path_in_image

    project = sanitize_project_id(session.github_username)
    env = per_notebook_env(
        slug=slug,
        mode=mode,  # type: ignore[arg-type]
        notebook_path=notebook_path,
        fork_owner=session.fork_owner,
        github_token=session.access_token,
        session_secret=_env("SESSION_SECRET"),
    )
    env.env_vars["FLYTE_PROJECT"] = project

    deployment = await flyte.with_servecontext(
        project=project, domain="development"
    ).serve.aio(env)
    _launched[session.github_username].add((slug, mode))
    return RedirectResponse(deployment.endpoint, status_code=303)


@asgi_app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Deploy entrypoint
# ---------------------------------------------------------------------------


def _build_and_push_notebook_image() -> None:
    """Build and push the `stargazer-note` image used by per-notebook apps.

    The admin pod cannot build images itself, so the deployer's machine
    must publish `stargazer-note:latest` to `STARGAZER_REGISTRY`
    before any user's `/launch` click can spawn a per-notebook app —
    the AppEnvironment image reference resolves at pod-pull time, not at
    deploy time.
    """
    tag = f"{os.environ['STARGAZER_REGISTRY']}/stargazer-note:latest"
    logger.info(f"Building notebook image {tag}")
    subprocess.run(
        ["docker", "build", "--target", "note", "-t", tag, str(PROJECT_ROOT)],
        check=True,
    )
    logger.info(f"Pushing notebook image {tag}")
    subprocess.run(["docker", "push", tag], check=True)


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
