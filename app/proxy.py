"""
### Reverse proxy in front of marimo, with workspace hydrate + sync.

Standalone ASGI app baked into the `notebook-app` image. Listens on the
per-notebook pod's public port (8080) and forwards HTTP + websocket traffic to
marimo on `127.0.0.1:8081`.

**Auth.** The pod runs behind the platform login (`requires_auth=True`), but
it also answers at an in-cluster address that skips the login, where any pod
in any project can send whatever headers it likes (measured 2026-10-18). So on
Union (`SG_AUTH_ISSUER` set) `_TokenGate` checks every HTTP and websocket
request for a token the issuer signed, `X-User-Token`, whose subject is the
owner (`SG_OWNER_SUBJECT`) or one of `SG_ADMIN_SUBJECTS`: 401 without one, 403
for anyone else. It mirrors `app.identity`, which this module can't import.
`SG_OWNER_SUBJECT` also keys where the pod hydrates from and saves to.
Platform cookies and `X-User-*` headers are stripped before anything reaches
marimo, so notebook code never sees the visitor's platform token through a
request.

**Workspace.** Every file in the user's workspace lives in the workspace store,
one object per file at its path, under
`<STARGAZER_WORKSPACE_ROOT>/users/<subject>/workspace/` — the layout
`app.workspace_store` owns (mirrored here because this module can't import the
`app` package). At launch, `hydrate()` copies the owner's whole workspace into
`/workspace`. While the pod runs, a background loop saves every file whose size
or modification time changed, every `SG_SAVE_INTERVAL_SECONDS` (5 by default,
0 for none), and deletes from the store the files deleted from `/workspace`. The `lifespan` shutdown hook
does a final pass when the pod scales to zero. Dotfiles, `__pycache__/`,
`__marimo__/` and files over `MAX_SAVED_BYTES` are never saved.

It also injects a Quake-style dropdown terminal into marimo's HTML: every
`text/html` response gets an xterm.js overlay (loaded from CDN) spliced in
before `</body>`, toggled with Ctrl+` and wired to the `/__sg__/term`
websocket below. Beside it goes a banner naming any file over
`MAX_SAVED_BYTES`, which isn't saved, with the cell that stores it as an
asset instead.

Reserved paths the proxy handles itself instead of forwarding:

- `GET /__sg__/dashboard` — 302 to the owner's dashboard (`STARGAZER_ADMIN_URL`), so
  notebooks can link back with a stable relative path.
- `GET /__sg__/save-status` — the files in `/workspace` over `MAX_SAVED_BYTES`,
  which aren't saved; the injected banner polls it.
- `GET /__sg__/ready` — 200 once local marimo answers, 503 while it's still
  cold-starting.
- `WS  /__sg__/term` — PTY websocket. Spawns a login `bash` and
  bridges it to the injected xterm.js overlay. The child's environment is
  scrubbed of secret-shaped vars; that's tidiness, not a boundary.

While marimo is still starting, a browser request gets a small self-refreshing
"Starting your notebook…" page instead of an error.

Self-contained on purpose: the notebook image installs `fastapi`, `uvicorn`,
`httpx` and `websockets` at system level next to the `flyte` SDK the base image
already carries (used here for storage), and COPYs this file in as
`/usr/local/lib/sg_proxy.py` (alongside its two HTML fragments) — no stargazer
or app-package install needed, and the top-level module name avoids colliding
with Flyte's loaded_modules code bundle which ships an `app/` package into the
pod's `/home/flyte` cwd at deploy time.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import termios
from contextlib import asynccontextmanager, suppress
from functools import cache
from pathlib import Path

import flyte
import flyte.storage
import httpx
import jwt
import websockets
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from starlette.background import BackgroundTask

MARIMO_HOST = "127.0.0.1"
MARIMO_HTTP_PORT = 8081
# The pod-local dir the launch hydrates into. Mirrors
# `app.per_notebook.WORKSPACE_NOTEBOOK_DIR`.
WORKSPACE_DIR = Path("/workspace")
# Never saved: Python's bytecode caches and marimo's per-notebook session caches.
_SKIPPED_DIRS = {"__pycache__", "__marimo__"}
# A file over this isn't saved with the workspace: big data belongs in the asset
# store, and the save at SIGTERM has to fit in the pod's grace period. The same
# limit as an upload through the dashboard's asset browser.
MAX_SAVED_BYTES = 100 * 1024**2

# Env keys never handed to the interactive shell. The suffix list catches future
# secret-shaped vars without an explicit entry per name. The org's Pinata key is
# in the notebook's env on purpose, but kept from the shell, where an agent's
# `env` would put it in the agent's context.
_TERM_SECRET_KEYS = {"PINATA_JWT"}
_TERM_SECRET_SUFFIXES = ("_SECRET", "_TOKEN", "_JWT", "_KEY", "_PASSWORD")

# Request headers that never reach marimo: the platform session cookies and the
# identity headers it injects (notably `X-User-Token`, the visitor's ID token).
_STRIPPED_PREFIXES = ("x-user-",)
_STRIPPED_HEADERS = {"host", "cookie"}

# Quake-style dropdown terminal markup, spliced into every marimo HTML page
# before </body>. Kept as a static asset (terminal_overlay.html) so it gets real
# HTML/CSS/JS tooling instead of living as a Python string. Read once at import.
# In the notebook image it's baked next to this module (see per_notebook.py), so
# resolving it relative to __file__ works both in-repo and in-pod.
_TERM_INJECTION = (Path(__file__).parent / "terminal_overlay.html").read_bytes()
# The notice naming files too big to save, spliced in the same way and baked
# beside it.
_SAVE_BANNER_INJECTION = (Path(__file__).parent / "save_banner.html").read_bytes()

_STARTING_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="2">
<title>Starting your notebook…</title>
<style>body{font-family:system-ui,sans-serif;background:#0b0b14;color:#ddd;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
</style></head>
<body><p>Starting your notebook… this page refreshes on its own.</p></body></html>
"""

# One shared client with keep-alive to the loopback marimo server, reused for
# every proxied request and readiness probe. Lazily created (import must stay
# side-effect-free for tests), closed by the lifespan hook at shutdown. Timeout
# is per-request: unbounded for proxied traffic (marimo holds long-poll
# connections), short for readiness probes.
_upstream: httpx.AsyncClient | None = None

# Relative path -> (size, mtime) of each file as it was last stored. Seeded at
# proxy startup from the freshly hydrated disk, so nothing re-uploads needlessly,
# and the set of files a pass may delete from the store.
_synced: dict[str, tuple[int, int]] = {}

_storage_ready = False


def _upstream_client() -> httpx.AsyncClient:
    """The shared keep-alive client for the local marimo backend."""
    global _upstream
    if _upstream is None:
        _upstream = httpx.AsyncClient(timeout=None)
    return _upstream


# ---------------------------------------------------------------------------
# Request headers
# ---------------------------------------------------------------------------


def _forwardable(headers) -> dict[str, str]:
    """Request headers safe to hand to marimo (no cookies, no identity)."""
    return {
        k: v
        for k, v in headers.items()
        if k.lower() not in _STRIPPED_HEADERS
        and not k.lower().startswith(_STRIPPED_PREFIXES)
    }


# ---------------------------------------------------------------------------
# Workspace store: hydrate at launch, sync while running and at shutdown
# ---------------------------------------------------------------------------


def _init_storage() -> None:
    """Configure the Flyte client in-cluster once, so storage credentials resolve.

    A no-op outside a pod (tests, local runs), where a plain path root needs no
    client at all.
    """
    global _storage_ready
    if _storage_ready:
        return
    if os.environ.get("_U_EP_OVERRIDE"):
        flyte.init_in_cluster()
    _storage_ready = True


def _user_prefix(kind: str) -> str | None:
    """`<root>/users/<owner>/<kind>`, or None when the store isn't configured.

    Same layout as `app.workspace_store.workspace_uri`.
    """
    root = os.environ.get("STARGAZER_WORKSPACE_ROOT", "").rstrip("/")
    owner = os.environ.get("SG_OWNER_SUBJECT", "")
    if not root or not owner:
        return None
    return f"{root}/users/{owner}/{kind}"


def _workspace_files() -> dict[str, Path]:
    """Every file in `/workspace` that's saved, by its POSIX path relative to it.

    Skips dotfiles and dot-dirs, Python's `__pycache__/`, and the session
    caches marimo writes in `__marimo__/`. Symlinks aren't followed, so a link
    to data elsewhere on the pod isn't copied into the store.
    """
    files: dict[str, Path] = {}
    for root, dirs, names in os.walk(WORKSPACE_DIR):
        dirs[:] = [d for d in dirs if not (d.startswith(".") or d in _SKIPPED_DIRS)]
        for name in names:
            path = Path(root) / name
            if name.startswith(".") or path.is_symlink():
                continue
            files[path.relative_to(WORKSPACE_DIR).as_posix()] = path
    return files


def _stamp(path: Path) -> tuple[int, int]:
    """A file's size and modification time, which say whether it changed."""
    st = path.stat()
    return st.st_size, st.st_mtime_ns


async def _download_prefix(prefix: str, dest: Path) -> int:
    """Copy every object under `prefix` to its relative path under `dest`.

    Returns how many were written. A missing prefix (a new user) writes none.
    """
    fs = flyte.storage.get_underlying_filesystem(path=prefix)
    try:
        entries = await asyncio.to_thread(fs.find, prefix)
    except FileNotFoundError:
        return 0
    # `find` names objects without the URI scheme (`bucket/key` on S3).
    base = fs._strip_protocol(prefix).rstrip("/") + "/"
    count = 0
    for entry in entries:
        rel = str(entry).removeprefix(base)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        chunks = [c async for c in flyte.storage.get_stream(f"{prefix}/{rel}")]
        target.write_bytes(b"".join(chunks))
        count += 1
    return count


async def hydrate_async() -> None:
    """Async body of `hydrate()`; also records the hydrated files as saved."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    prefix = _user_prefix("workspace")
    if prefix is None:
        print("[sg] workspace store not configured; starting with an empty workspace")
        return
    _init_storage()
    n = await _download_prefix(prefix, WORKSPACE_DIR)
    print(f"[sg] hydrated {n} file(s)")
    _seed_from_disk()


def hydrate() -> None:
    """Fill `/workspace` from the owner's stored workspace.

    Run by the launch script, as its own process, before marimo starts, so the
    notebook marimo opens already exists on disk. Always leaves the dir in
    place, empty for a new user or an unconfigured store.
    """
    asyncio.run(hydrate_async())


def _seed_from_disk() -> None:
    """Record every file now in `/workspace` as already stored.

    Called at proxy startup, right after hydration, so the first pass doesn't
    re-upload what was just downloaded. It's also what a later pass may
    delete from the store: only files this pod knew about. After a failed
    hydrate the workspace is empty, so nothing stored is ever deleted.
    """
    if not WORKSPACE_DIR.is_dir():
        return
    for rel, path in _workspace_files().items():
        _synced.setdefault(rel, _stamp(path))


async def _upload(uri: str, data: bytes) -> None:
    """Write one file's bytes as one object (one PUT, atomic per object)."""
    parent = uri.rsplit("/", 1)[0]
    # Object stores have no directories; a local root does. A no-op on S3.
    fs = flyte.storage.get_underlying_filesystem(path=parent)
    await asyncio.to_thread(fs.makedirs, parent, exist_ok=True)
    await flyte.storage.put_stream(data, to_path=uri)


def _delete_sync(uri: str) -> None:
    """Remove one object; one already gone counts as deleted."""
    with suppress(FileNotFoundError):
        flyte.storage.get_underlying_filesystem(path=uri).rm(uri)


async def sync_once() -> list[str]:
    """Save every changed file in `/workspace`; return their relative paths.

    A file whose size and modification time match what was last stored isn't
    read at all, and nor is one over `MAX_SAVED_BYTES`. A file deleted from `/workspace` is deleted from the store,
    if this pod hydrated or saved it. A failed upload or delete is logged and
    retried on the next pass rather than raised.
    """
    prefix = _user_prefix("workspace")
    if prefix is None or not WORKSPACE_DIR.is_dir():
        return []
    _init_storage()
    files = _workspace_files()
    saved = []
    for rel, path in sorted(files.items()):
        try:
            stamp = _stamp(path)
            if _synced.get(rel) == stamp or stamp[0] > MAX_SAVED_BYTES:
                continue
            await _upload(f"{prefix}/{rel}", path.read_bytes())
        except Exception as exc:
            print(f"[sg] saving {rel} failed: {exc}")
            continue
        _synced[rel] = stamp
        saved.append(rel)
    deleted = []
    for rel in sorted(_synced.keys() - files.keys()):
        try:
            await asyncio.to_thread(_delete_sync, f"{prefix}/{rel}")
        except Exception as exc:
            print(f"[sg] deleting {rel} failed: {exc}")
            continue
        del _synced[rel]
        deleted.append(rel)
    if saved:
        print(f"[sg] saved {', '.join(saved)}")
    if deleted:
        print(f"[sg] deleted {', '.join(deleted)}")
    return saved


def _save_interval() -> float:
    """Seconds between save passes, from the pod's env; 0 means none.

    Nothing sets it yet, so pods save every 5 seconds; ticket
    `dashboard-settings` has the dashboard set it per user. The pass reads
    only files whose size or mtime changed, so a short interval costs little
    and bounds what a pod that dies without SIGTERM loses.
    """
    return float(os.environ.get("SG_SAVE_INTERVAL_SECONDS", "5"))


async def _sync_loop(interval: float) -> None:
    """Save every `interval` seconds for the life of the pod."""
    while True:
        await asyncio.sleep(interval)
        try:
            await sync_once()
        except Exception as exc:  # keep the loop alive whatever happens
            print(f"[sg] workspace sync pass failed: {exc}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run the save loop while serving; flush pending edits on shutdown.

    `/workspace` is ephemeral, so anything not written before the pod idles is
    lost. With the interval at 0 there's no loop, and this flush is the only
    save. Flyte's `fserve` wrapper is PID 1 and forwards the Knative SIGTERM to
    its one direct child; the launch script's `exec` chain (args prepend `exec`,
    then the script `exec`s uvicorn) makes uvicorn that direct child, so it
    receives SIGTERM and runs this hook. See app/launch-notebook.sh — an
    intermediate shell anywhere in that chain would swallow the signal and skip
    this flush.
    """
    _seed_from_disk()
    interval = _save_interval()
    loop_task = asyncio.create_task(_sync_loop(interval)) if interval > 0 else None
    yield
    if loop_task is not None:
        loop_task.cancel()
        with suppress(asyncio.CancelledError):
            await loop_task
    try:
        await sync_once()
    except Exception as exc:  # never block shutdown
        print(f"[sg] workspace shutdown sync failed: {exc}")
    global _upstream
    if _upstream is not None:
        await _upstream.aclose()
        _upstream = None


# Clock skew allowed on a token's expiry and not-before times.
_LEEWAY_SECONDS = 60


@cache
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    """The issuer's signing keys, found from its discovery document."""
    discovery = httpx.get(f"{issuer}/.well-known/openid-configuration", timeout=10)
    discovery.raise_for_status()
    # An hour between refreshes: a token signed by a key not yet cached
    # refetches the set anyway, and the first fetch blocks the request.
    return jwt.PyJWKClient(discovery.json()["jwks_uri"], lifespan=3600)


def _signing_key(token: str):
    """The issuer's public key that signed `token`."""
    return (
        _jwks_client(os.environ["SG_AUTH_ISSUER"]).get_signing_key_from_jwt(token).key
    )


def _refusal(headers: dict[bytes, bytes]) -> int | None:
    """The status that turns a request away, or None to let it through.

    401 without a token the issuer signed that hasn't expired; 403 for a
    subject other than the owner or an admin.
    """
    _, _, token = headers.get(b"x-user-token", b"").decode().partition(" ")
    if not token:
        return 401
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            issuer=os.environ["SG_AUTH_ISSUER"],
            leeway=_LEEWAY_SECONDS,
            options={"require": ["exp", "iss", "sub"], "verify_aud": False},
        )
    except jwt.PyJWTError:
        return 401
    admins = os.environ.get("SG_ADMIN_SUBJECTS", "").split(",")
    allowed = {os.environ.get("SG_OWNER_SUBJECT", ""), *admins} - {""}
    return None if claims["sub"] in allowed else 403


class _TokenGate:
    """ASGI middleware: on Union, a request `_refusal` turns away goes no further.

    An HTTP request gets the status; a websocket is closed with 1008 (policy
    violation) before it's accepted. Off when `SG_AUTH_ISSUER` is unset.
    """

    def __init__(self, app):
        """Wrap `app`."""
        self.app = app

    async def __call__(self, scope, receive, send):
        """Check the request, then pass it on or refuse it."""
        if scope["type"] in ("http", "websocket") and os.environ.get("SG_AUTH_ISSUER"):
            # Off the event loop: the first check fetches the issuer's keys.
            status = await asyncio.to_thread(_refusal, dict(scope["headers"]))
            if status is not None:
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                    return
                body = b"not signed in" if status == 401 else b"not your notebook"
                await send(
                    {
                        "type": "http.response.start",
                        "status": status,
                        "headers": [(b"content-type", b"text/plain")],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


asgi_app = FastAPI(
    title="stargazer-notebook-proxy", docs_url=None, redoc_url=None, lifespan=lifespan
)
asgi_app.add_middleware(_TokenGate)


# ---------------------------------------------------------------------------
# Reserved /__sg__/* endpoints (handled locally, NOT forwarded to marimo).
# Declared before the catch-all proxy routes so FastAPI matches them first.
# ---------------------------------------------------------------------------


@asgi_app.get("/__sg__/dashboard")
async def dashboard_redirect() -> Response:
    """Redirect back to the owner's dashboard (`STARGAZER_ADMIN_URL`).

    The dashboard and the notebook live on different hosts, so a notebook can't just
    link to `/`. It reveals nothing.
    """
    target = os.environ.get("STARGAZER_ADMIN_URL") or "/"
    return RedirectResponse(target, status_code=302)


@asgi_app.get("/__sg__/save-status")
async def save_status() -> dict:
    """The files in `/workspace` too big to save, for the injected banner.

    Read from disk on each request rather than from the last save pass, so the
    banner works with the periodic save turned off too.
    """
    unsaved = []
    if WORKSPACE_DIR.is_dir():
        for rel, path in sorted(_workspace_files().items()):
            with suppress(FileNotFoundError):
                size = path.stat().st_size
                if size > MAX_SAVED_BYTES:
                    unsaved.append({"path": rel, "bytes": size})
    return {"limit_bytes": MAX_SAVED_BYTES, "unsaved": unsaved}


@asgi_app.get("/__sg__/ready")
async def ready() -> Response:
    """200 once local marimo answers, else 503."""
    try:
        resp = await _upstream_client().get(
            f"http://{MARIMO_HOST}:{MARIMO_HTTP_PORT}/", timeout=2.0
        )
        if resp.status_code < 500:
            return Response("ready", status_code=200)
    except Exception:
        pass
    return Response("not ready", status_code=503)


def _shell_env() -> dict[str, str]:
    """Pod env with auth-critical secrets stripped, for the interactive shell.

    Drops every key in `_TERM_SECRET_KEYS` plus anything ending in a
    secret-shaped suffix, so credentials stay out of casual `env` output. Not a boundary (see the module docstring). Sets a sane `TERM` so curses apps render.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in _TERM_SECRET_KEYS and not k.endswith(_TERM_SECRET_SUFFIXES)
    }
    env.setdefault("TERM", "xterm-256color")
    return env


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    """Apply an xterm.js fit-addon size to the PTY via TIOCSWINSZ.

    Keeps the shell's notion of the terminal geometry in sync with the browser
    pane so line wrapping and full-screen TUIs (less, vim) lay out correctly.
    """
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


@asgi_app.websocket("/__sg__/term")
async def term_proxy(websocket: WebSocket) -> None:
    """Bridge the injected xterm.js overlay to a login bash via a PTY.

    Forks a `bash -l` on a pseudo-terminal
    with a secret-scrubbed environment (`_shell_env`) and pumps bytes both ways:
    PTY output is read off the master fd (registered with the event loop) and
    sent as binary frames; the client sends JSON text frames — `{"type":
    "input", ...}` for keystrokes and `{"type": "resize", ...}` for geometry.
    The child is killed and reaped when either side closes.
    """
    await websocket.accept()

    pid, master_fd = pty.fork()
    if pid == 0:  # child — becomes the shell
        try:
            os.execvpe("/bin/bash", ["/bin/bash", "-l"], _shell_env())
        except Exception:
            pass
        os._exit(1)  # exec failed

    loop = asyncio.get_running_loop()
    os.set_blocking(master_fd, False)
    queue: asyncio.Queue[bytes] = asyncio.Queue()

    def _on_readable() -> None:
        """Drain the PTY master fd into the outbound queue (b'' on EOF/error)."""
        try:
            data = os.read(master_fd, 65536)
        except OSError:
            data = b""
        queue.put_nowait(data)

    loop.add_reader(master_fd, _on_readable)

    async def pump_out() -> None:
        """Forward queued PTY output to the browser until EOF."""
        while True:
            data = await queue.get()
            if not data:
                return
            await websocket.send_bytes(data)

    async def pump_in() -> None:
        """Apply client input/resize JSON frames to the PTY until disconnect."""
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                return
            raw = msg.get("text")
            if raw is None:
                continue
            try:
                payload = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if payload.get("type") == "input":
                os.write(master_fd, payload.get("data", "").encode())
            elif payload.get("type") == "resize":
                _set_winsize(
                    master_fd,
                    int(payload.get("rows", 24)),
                    int(payload.get("cols", 80)),
                )

    out_task = asyncio.create_task(pump_out())
    in_task = asyncio.create_task(pump_in())
    try:
        _done, pending = await asyncio.wait(
            {out_task, in_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    finally:
        loop.remove_reader(master_fd)
        os.close(master_fd)
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Catch-all HTTP + websocket proxy → marimo on 127.0.0.1:8081
# ---------------------------------------------------------------------------


# Hop-by-hop headers that must never be relayed (Starlette/uvicorn manage the
# connection and framing themselves).
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


@asgi_app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def http_proxy(request: Request, path: str) -> Response:
    """Forward any HTTP method to marimo on localhost:8081.

    Runs on the shared keep-alive client. Platform cookies and identity headers
    are dropped before forwarding. Only `text/html` responses are buffered —
    the dropdown-terminal overlay is spliced in before `</body>` (app chrome on
    every page, no marimo plugin needed). Everything else — static bundles, API
    JSON, downloads — streams through chunk-by-chunk with its original headers,
    so large bodies never sit in proxy memory. The raw query string passes
    through untouched (duplicate params intact). While marimo is still starting,
    browsers get a self-refreshing starting page and other callers a plain 503.
    """
    upstream = f"http://{MARIMO_HOST}:{MARIMO_HTTP_PORT}/{path}"
    if request.url.query:
        upstream = f"{upstream}?{request.url.query}"
    headers = _forwardable(request.headers)
    # Stream the request body through only when there is one — chunked framing
    # on a bodyless GET would be gratuitous.
    has_body = "content-length" in request.headers or (
        "transfer-encoding" in request.headers
    )
    client = _upstream_client()
    req = client.build_request(
        request.method,
        upstream,
        headers=headers,
        content=request.stream() if has_body else None,
    )
    try:
        resp = await client.send(req, stream=True)
    except httpx.ConnectError:
        if "text/html" in request.headers.get("accept", ""):
            return HTMLResponse(_STARTING_PAGE, status_code=503)
        return Response("Notebook is starting", status_code=503)

    if "text/html" in resp.headers.get("content-type", "").lower():
        # Buffer + splice the terminal overlay. `aread()` decodes any
        # content-encoding, and the injection changes the size, so drop both
        # headers and let Starlette recompute the length.
        content = await resp.aread()
        await resp.aclose()
        content = content.replace(
            b"</body>", _TERM_INJECTION + _SAVE_BANNER_INJECTION + b"</body>", 1
        )
        forbidden = _HOP_BY_HOP | {"content-encoding", "content-length"}
        out_headers = {
            k: v for k, v in resp.headers.items() if k.lower() not in forbidden
        }
        return Response(
            content=content, status_code=resp.status_code, headers=out_headers
        )

    # Non-HTML: stream the raw (still-encoded) bytes through, keeping
    # content-length/content-encoding — the byte count is unchanged.
    async def _relay():
        """Relay upstream bytes; a pre-buffered response (e.g. a canned test
        transport) has no live stream left, so fall back to its content."""
        if resp.is_stream_consumed:
            yield resp.content
            return
        async for chunk in resp.aiter_raw():
            yield chunk

    out_headers = {
        k: v for k, v in resp.headers.items() if k.lower() not in _HOP_BY_HOP
    }
    return StreamingResponse(
        _relay(),
        status_code=resp.status_code,
        headers=out_headers,
        background=BackgroundTask(resp.aclose),
    )


@asgi_app.websocket("/{path:path}")
async def ws_proxy(websocket: WebSocket, path: str) -> None:
    """Bridge a client websocket to marimo's websocket.

    The upstream connection is opened without the client's headers, so no
    cookie or identity header reaches marimo here either.
    """
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
                    if (data := msg.get("text")) is not None or (
                        data := msg.get("bytes")
                    ) is not None:
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
