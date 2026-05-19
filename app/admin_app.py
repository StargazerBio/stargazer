"""
### Stargazer admin landing app.

Single shared FastAPI service: GitHub OAuth, per-user Flyte project +
notebook app provisioning, and a dashboard that links each authenticated
user to their own `notebook` app in project `sg-<username>`. The notebook
itself is NOT served by this process — `provision_user()` deploys the
`notebook_env` AppEnvironment into the user's project on first login and
stores the resulting URL on the session cookie.

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
from contextlib import asynccontextmanager

import flyte
import flyte.app
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from stargazer.config import (
    PROJECT_ROOT,
    STARGAZER_ENV_VARS,
    logger,
)

from app.init import init
from app.oauth import exchange_code, get_github_user, github_auth_url
from app.provision import provision_user
from app.session import (
    SESSION_COOKIE,
    SessionData,
    create_session_cookie,
    read_session_cookie,
)
from app.templates import dashboard_html, login_html, provisioning_html


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
# per-user `serve.aio(notebook_env)` calls. `with_servecontext(project=...)`
# alone is not enough — the upload uses the client's init-time project.
_FLYTE_CONTEXT = {
    "FLYTE_PROJECT": os.environ.get("FLYTE_PROJECT", "flytesnacks"),
    "FLYTE_DOMAIN": os.environ.get("FLYTE_DOMAIN", "development"),
}


app_env = flyte.app.AppEnvironment(
    name="admin-app",
    description="Admin landing + per-user notebook provisioning",
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
    """Initialize Flyte client so provision_user() can call flyte.serve()."""
    init()
    yield


asgi_app = FastAPI(
    title="Stargazer", docs_url=None, redoc_url=None, lifespan=lifespan
)


def _redirect_uri(request: Request) -> str:
    """Build the OAuth callback URI."""
    base = os.environ.get("LANDING_BASE_URL")
    if base:
        return f"{base.rstrip('/')}/auth/callback"
    return str(request.url_for("auth_callback"))


def _get_session(request: Request) -> SessionData | None:
    """Extract a valid session from the request cookie, if present."""
    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        return None
    return read_session_cookie(cookie, _env("SESSION_SECRET"))


@asgi_app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Login / provisioning / dashboard depending on session state."""
    session = _get_session(request)
    if not session:
        return HTMLResponse(login_html())
    if not session.notebook_url:
        return HTMLResponse(provisioning_html(session.github_username))
    return HTMLResponse(
        dashboard_html(session.github_username, session.notebook_url)
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
        notebook_url = await provision_user(username)
    except Exception as exc:
        logger.error(f"Provisioning failed for {username!r}: {exc}")
        notebook_url = None

    session = SessionData(
        github_username=username,
        github_id=github_user["id"],
        notebook_url=notebook_url,
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


@asgi_app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Deploy entrypoint
# ---------------------------------------------------------------------------


def _build_and_push_notebook_image() -> None:
    """Build and push the `stargazer-note` image consumed by `notebook_env`.

    The admin pod cannot build images itself, so the deployer's machine
    must publish `stargazer-note:latest` to `STARGAZER_REGISTRY` before
    per-user `flyte.serve.aio(notebook_env)` calls can pull it.
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
    init(root_dir=PROJECT_ROOT)
    _start_storage_port_forward()
    _build_and_push_notebook_image()
    deployment = flyte.serve(app_env)
    print(f"App URL: {deployment.endpoint}")


if __name__ == "__main__":
    main()
