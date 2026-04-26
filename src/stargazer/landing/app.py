"""
### FastAPI landing page application.

Handles GitHub OAuth login, per-user project provisioning, and serves
as the entry point at app.stargazer.bio. Both the FastAPI app and the
Flyte AppEnvironment for deployment live here, mirroring the marimo
notebook pattern in stargazer.app.

Local development:
    uvicorn stargazer.landing.app:app --reload --port 8080

Run locally via Flyte:
    stargazer-landing

spec: [docs/architecture/landing.md](../../docs/architecture/landing.md)
"""

import os
import secrets
import sys
from pathlib import Path

import flyte
import flyte.app
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from stargazer.config import LANDING_SECRETS, STARGAZER_ENV_VARS
from stargazer.landing.oauth import exchange_code, get_github_user, github_auth_url
from stargazer.landing.provision import provision_user, sanitize_project_id
from stargazer.landing.session import (
    SESSION_COOKIE,
    SessionData,
    create_session_cookie,
    read_session_cookie,
)
from stargazer.landing.templates import dashboard_html, login_html, provisioning_html

app = FastAPI(title="Stargazer", docs_url=None, redoc_url=None)


def _env(key: str) -> str:
    """Read a required environment variable."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Missing required env var: {key}")
    return value


def _redirect_uri(request: Request) -> str:
    """Build the OAuth callback URI.

    Prefers LANDING_BASE_URL when set (avoids proxy-induced host/scheme
    drift); falls back to deriving from the request.
    """
    base = os.environ.get("LANDING_BASE_URL")
    if base:
        return f"{base.rstrip('/')}/auth/callback"
    return str(request.url_for("auth_callback"))


def _get_session(request: Request) -> SessionData | None:
    """Extract session from the request cookie, if valid."""
    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        return None
    return read_session_cookie(cookie, _env("SESSION_SECRET"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Landing page or dashboard depending on session state."""
    session = _get_session(request)
    if session and session.notebook_url:
        project_id = sanitize_project_id(session.github_username)
        console_url = os.environ.get("UNION_CONSOLE_URL")
        if console_url:
            console_url = f"{console_url}/projects/{project_id}/executions"
        return HTMLResponse(
            dashboard_html(session.github_username, session.notebook_url, console_url)
        )
    if session and not session.notebook_url:
        return HTMLResponse(provisioning_html(session.github_username))
    return HTMLResponse(login_html())


@app.get("/auth/login")
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
        "oauth_state", state, httponly=True, secure=True, max_age=600, samesite="lax"
    )
    return response


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str, state: str):
    """Handle the GitHub OAuth callback."""
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
    user_id = github_user["id"]
    notebook_url = await provision_user(username)

    session = SessionData(
        github_username=username,
        github_id=user_id,
        notebook_url=notebook_url,
    )
    cookie = create_session_cookie(session, _env("SESSION_SECRET"))
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        cookie,
        httponly=True,
        secure=True,
        max_age=60 * 60 * 24 * 30,
        samesite="lax",
    )
    response.delete_cookie("oauth_state")
    return response


@app.get("/auth/logout")
async def auth_logout():
    """Clear session and redirect to landing page."""
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Flyte AppEnvironment
# ---------------------------------------------------------------------------

landing_env = flyte.app.AppEnvironment(
    name="stargazer-landing",
    image=flyte.Image.from_debian_base(python_version=(3, 13)).with_pip_packages(
        "stargazer[landing]",
    ),
    args=[sys.executable, "src/stargazer/landing/app.py", "--server"],
    port=8080,
    include=["src/stargazer/landing/"],
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    requires_auth=False,
    env_vars=STARGAZER_ENV_VARS,
    secrets=LANDING_SECRETS,
)


def _run_server():
    """Start uvicorn serving the FastAPI app."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)


def main():
    """Deploy the landing page to Flyte."""
    import signal

    from stargazer.init import init

    init(root_dir=Path(__file__).parent.parent)
    deployment = flyte.serve(landing_env)
    print(f"Landing URL: {deployment.url}")

    def _shutdown(signum, frame):
        """Handle SIGINT/SIGTERM by killing the entire process group."""
        pid = deployment._process.pid
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        deployment.deactivate(wait=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    deployment._process.wait()


if __name__ == "__main__":
    if "--server" in sys.argv:
        _run_server()
    else:
        main()
