"""
### Cookie-validating reverse proxy in front of marimo, with workspace endpoints.

Standalone ASGI app baked into the `notebook-app` image. Listens on
the per-notebook pod's public port (8080), validates the same signed
session cookie the admin app issues (HMAC-keyed by `SESSION_SECRET`),
then forwards HTTP + websocket traffic to marimo on `127.0.0.1:8081`.

Four reserved paths the proxy handles itself instead of forwarding:

- `GET  /__sg__/dashboard` — 302 to the admin app's URL (read from
  `STARGAZER_ADMIN_URL`). Lets notebooks link back to the dashboard
  with a stable relative path instead of plumbing the admin URL into
  each notebook's Python.
- `GET  /__sg__/ready` — unauthenticated readiness probe; returns 200
  once local marimo answers, 503 while it's still cold-starting. Polled
  by the admin app's `/launch` handler so the dashboard spinner only
  resolves once the pod is actually serving.
- `GET  /__sg__/workspace/list` — directory listing of the user's
  workspace from the pod-local `/workspace` clone of their fork. Admin
  app queries this on dashboard render so workspace state is read
  straight off disk.
- `POST /__sg__/workspace/sync` — `git add` + `git commit` + `git push`
  to the fork's `main` using the `GITHUB_TOKEN`/`FORK_OWNER` baked into
  env_vars at deploy time. Only the `notebooks/workspace/` dir is staged,
  so the fork's `main` never collides with upstream's shipped files.
  Called by the launch script's SIGTERM hook on idle-down, and exposed to
  the admin app as a "save" affordance.

Self-contained on purpose: the notebook image installs only `fastapi`,
`uvicorn`, `itsdangerous`, `httpx`, `websockets` at system level and
COPYs this single file in as `/usr/local/lib/sg_proxy.py` — no
stargazer or app-package install needed, and the top-level module
name avoids colliding with Flyte's loaded_modules code bundle which
ships an `app/` package into the pod's `/home/flyte` cwd at deploy
time.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import asyncio
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

import httpx
import websockets
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer


SESSION_COOKIE = "sg_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days, matches app.session
LAUNCH_QUERY_PARAM = "sg_launch"
MARIMO_HOST = "127.0.0.1"
MARIMO_HTTP_PORT = 8081
WORKSPACE_ROOT = Path("/workspace")
WORKSPACE_NOTEBOOK_DIR = WORKSPACE_ROOT / "src/stargazer/notebooks/workspace"
WORKSPACE_REL = "src/stargazer/notebooks/workspace"


def _sync_workspace() -> tuple[dict, int]:
    """git add + commit + push the workspace dir to the user's fork.

    Returns `(payload, http_status)`. `{"status": "clean"}` means there were
    no on-disk changes to push. Shared by the `/__sg__/workspace/sync` route
    and the shutdown hook so manual Save and scale-to-zero use one code path.
    """
    if not (WORKSPACE_ROOT / ".git").exists():
        return {"error": "workspace not initialized"}, 409

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(WORKSPACE_ROOT), *args], capture_output=True, text=True
        )

    add = git("add", WORKSPACE_REL)
    if add.returncode != 0:
        return {"error": "git add failed", "stderr": add.stderr}, 500
    status = git("status", "--porcelain", WORKSPACE_REL)
    if not status.stdout.strip():
        return {"status": "clean"}, 200
    # Name the touched notebook(s) in the message — the porcelain paths are the
    # only authoritative signal here (the pod isn't told its own slug). For
    # renames ("R old -> new") the last token is the new path.
    saved = sorted(
        {Path(line.split()[-1]).stem for line in status.stdout.splitlines() if line.strip()}
    )
    commit = git("commit", "-m", f"workspace: save {', '.join(saved)}")
    if commit.returncode != 0:
        return {"error": "git commit failed", "stderr": commit.stderr}, 500
    push = git("push", "origin", "HEAD:main")
    if push.returncode != 0:
        return {"error": "git push failed", "stderr": push.stderr}, 500
    return {"status": "pushed"}, 200


@asynccontextmanager
async def lifespan(_: FastAPI):
    """On shutdown (Knative SIGTERM at scale-to-zero), flush pending edits.

    `/workspace` is ephemeral, so anything not pushed before the pod idles is
    lost. uvicorn runs as PID 1 (the launch script `exec`s it), so it receives
    SIGTERM and runs this hook — unlike the launch script's shell trap, which
    `exec` discards.
    """
    yield
    try:
        payload, _code = await asyncio.to_thread(_sync_workspace)
        print(f"[sg] workspace shutdown sync: {payload}")
    except Exception as exc:  # never block shutdown
        print(f"[sg] workspace shutdown sync failed: {exc}")


asgi_app = FastAPI(
    title="stargazer-notebook-proxy", docs_url=None, redoc_url=None, lifespan=lifespan
)


def _cookie_is_valid(cookie_value: str | None) -> bool:
    """Verify the signed session cookie against `SESSION_SECRET`.

    Returns False (denying access) if the secret env var is missing, the
    cookie is absent, or the signature does not verify within the max
    age window.
    """
    secret = os.environ.get("SESSION_SECRET")
    if not secret or not cookie_value:
        return False
    try:
        URLSafeTimedSerializer(secret).loads(cookie_value, max_age=SESSION_MAX_AGE)
        return True
    except (BadSignature, Exception):
        return False


@asgi_app.middleware("http")
async def redeem_launch_token(request: Request, call_next):
    """Convert an `?sg_launch=<token>` URL into a host-only session cookie.

    The admin app at `admin-…<parent>` and this per-notebook host at
    `nb-…<parent>` are sibling subdomains that intentionally use host-only
    cookies (no shared `Domain=` parent), so a notebook can't read the admin's
    cookie. So `/launch` redirects here with the signed session value as a
    one-shot query param; we set our own host-only cookie and bounce the
    browser to the clean URL.
    """
    token = request.query_params.get(LAUNCH_QUERY_PARAM)
    if not token or not _cookie_is_valid(token):
        return await call_next(request)
    remaining = {
        k: v for k, v in request.query_params.multi_items() if k != LAUNCH_QUERY_PARAM
    }
    clean = request.url.path + (f"?{urlencode(remaining)}" if remaining else "")
    response = RedirectResponse(clean, status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=False,
        max_age=SESSION_MAX_AGE,
        samesite="lax",
    )
    return response


# ---------------------------------------------------------------------------
# Reserved /__sg__/* endpoints (handled locally, NOT forwarded to marimo).
# Declared before the catch-all proxy routes so FastAPI matches them first.
# ---------------------------------------------------------------------------


@asgi_app.get("/__sg__/dashboard")
async def dashboard_redirect() -> Response:
    """Redirect back to the admin dashboard.

    Admin and per-notebook live on sibling subdomains, so a notebook
    can't just link to `/`. The admin pod stamps its own URL into the
    per-notebook's `STARGAZER_ADMIN_URL` env var at launch time; this
    route just 302s the browser there. No cookie check — the dashboard
    is the place users go to *re*-authenticate.
    """
    target = os.environ.get("STARGAZER_ADMIN_URL") or "/"
    return RedirectResponse(target, status_code=302)


@asgi_app.get("/__sg__/ready")
async def ready() -> Response:
    """Probe local marimo on 127.0.0.1:8081; 200 if reachable, else 503.

    Polled cross-origin from the dashboard JS so the spinner can resolve
    once the pod is actually serving. The probe runs from the browser (which
    already has a route to the notebook URL) rather than the admin pod, so
    readiness is judged from the same vantage point the user will open from.
    Hence the `Access-Control-Allow-Origin: *` header — readiness leaks no
    data so wildcard is fine. Unauthenticated by design.
    """
    headers = {"Access-Control-Allow-Origin": "*"}
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"http://{MARIMO_HOST}:{MARIMO_HTTP_PORT}/")
        if resp.status_code < 500:
            return Response("ready", status_code=200, headers=headers)
    except Exception:
        pass
    return Response("not ready", status_code=503, headers=headers)


@asgi_app.get("/__sg__/workspace/list")
async def workspace_list(request: Request) -> Response:
    """Return `.py` filenames in the locally-mounted workspace dir."""
    if not _cookie_is_valid(request.cookies.get(SESSION_COOKIE)):
        return Response("Unauthorized", status_code=401)
    if not WORKSPACE_NOTEBOOK_DIR.exists():
        return JSONResponse({"files": []})
    files = sorted(
        p.name
        for p in WORKSPACE_NOTEBOOK_DIR.glob("*.py")
        if not p.name.startswith("_")
    )
    return JSONResponse({"files": files})


@asgi_app.post("/__sg__/workspace/sync")
async def workspace_sync(request: Request) -> Response:
    """Commit + push pending workspace edits to the user's fork (manual Save).

    Invoked by the admin app's `/workspace/save` with the user's session
    cookie. Idle/shutdown flushes go through the proxy's `lifespan` hook
    instead, which calls `_sync_workspace` directly (no HTTP round-trip).
    """
    if not _cookie_is_valid(request.cookies.get(SESSION_COOKIE)):
        return Response("Unauthorized", status_code=401)
    payload, code = await asyncio.to_thread(_sync_workspace)
    return JSONResponse(payload, status_code=code)


# ---------------------------------------------------------------------------
# Catch-all HTTP + websocket proxy → marimo on 127.0.0.1:8081
# ---------------------------------------------------------------------------


@asgi_app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def http_proxy(request: Request, path: str) -> Response:
    """Forward any HTTP method to marimo on localhost:8081 after cookie check."""
    if not _cookie_is_valid(request.cookies.get(SESSION_COOKIE)):
        return Response("Unauthorized", status_code=401)

    upstream = f"http://{MARIMO_HOST}:{MARIMO_HTTP_PORT}/{path}"
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}

    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.request(
            request.method,
            upstream,
            params=dict(request.query_params),
            headers=headers,
            content=body,
        )
    # Strip hop-by-hop headers that httpx may carry across.
    forbidden = {"content-encoding", "transfer-encoding", "connection"}
    out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in forbidden}
    return Response(
        content=resp.content, status_code=resp.status_code, headers=out_headers
    )


@asgi_app.websocket("/{path:path}")
async def ws_proxy(websocket: WebSocket, path: str) -> None:
    """Bridge a client websocket to marimo's websocket after cookie check."""
    if not _cookie_is_valid(websocket.cookies.get(SESSION_COOKIE)):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    upstream_url = f"ws://{MARIMO_HOST}:{MARIMO_HTTP_PORT}/{path}"
    if websocket.url.query:
        upstream_url = f"{upstream_url}?{websocket.url.query}"

    async with websockets.connect(upstream_url) as upstream:

        async def client_to_upstream() -> None:
            """Pump frames from the browser to marimo."""
            try:
                while True:
                    msg = await websocket.receive()
                    if msg["type"] == "websocket.disconnect":
                        return
                    if (data := msg.get("text")) is not None:
                        await upstream.send(data)
                    elif (data := msg.get("bytes")) is not None:
                        await upstream.send(data)
            except Exception:
                return

        async def upstream_to_client() -> None:
            """Pump frames from marimo back to the browser."""
            try:
                async for msg in upstream:
                    if isinstance(msg, bytes):
                        await websocket.send_bytes(msg)
                    else:
                        await websocket.send_text(msg)
            except Exception:
                return

        await asyncio.gather(client_to_upstream(), upstream_to_client())
