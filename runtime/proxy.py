"""
### Reverse proxy in front of marimo, with workspace hydrate + sync.

Standalone ASGI app baked into the Stargazer image as the top-level module
`/usr/local/lib/sg_proxy.py`, beside its two HTML fragments. It imports no
stargazer code: it runs in the image's runtime venv (the project's `runtime`
group), with the `flyte` SDK for storage. Listens on the per-notebook pod's
public port (8080) and forwards HTTP + websocket traffic to marimo on
`127.0.0.1:8081`.

**Auth.** The pod runs behind the platform login (`requires_auth=True`), but
it also answers at an in-cluster address that skips the login, where any pod
in any project can send whatever headers it likes (measured 2026-10-18). So on
Union (`SG_AUTH_ISSUER` set) `_TokenGate` checks every HTTP and websocket
request for a token the issuer signed, `X-User-Token`, whose subject is the
owner (`SG_OWNER_SUBJECT`) or one of `SG_ADMIN_SUBJECTS`: 401 without one, 403
for anyone else. The dashboard checks its own requests the same way.
`SG_OWNER_SUBJECT` also keys where the pod hydrates from and saves to.
Platform cookies and `X-User-*` headers are stripped before anything reaches
marimo, so notebook code never sees the visitor's platform token through a
request.

**Workspace.** Every file in the user's workspace lives in the workspace store,
one object per file at its path, under
`<STARGAZER_WORKSPACE_ROOT>/users/<subject>/workspace/`, a layout the dashboard
reads and writes too (the pod contract in the runtime doc). At launch, `hydrate()` copies the owner's whole workspace into
`/workspace`. While the pod runs, a background loop saves every file whose size
or modification time changed, every `SG_SAVE_INTERVAL_SECONDS` (30 by default,
0 for none), and deletes from the store the files deleted from `/workspace`.
A file it holds that's gone from the store was deleted there, by the
dashboard, and isn't put back, and nor is the blank marimo opens for a
notebook that didn't hydrate (`SG_UNSAVED_NOTEBOOK`).
The `lifespan` shutdown hook does a final pass when the pod scales to zero.
Dotfiles, `__pycache__/`, `__marimo__/` and files over `MAX_SAVED_BYTES` are
never saved.

**Sign-ins.** The agents' sign-ins (`AGENT_SIGN_INS`, in the home directory)
are kept the same way under `<STARGAZER_WORKSPACE_ROOT>/users/<subject>/agents/`,
beside the workspace rather than in it, so they never show up among the user's
files: put back at launch, readable by the owner alone, saved by the same
passes when they change, and deleted from the store on a sign-out.

**Agents.** The terminal and the agents are marimo's own. marimo's agent panel
dials each agent at a fixed port on the page's host, which a hosted pod
doesn't serve, so every `text/html` response gets a script spliced in before
`</body>` that points Claude Code's and OpenCode's at `/__sg__/agent/<name>`
below. Beside it goes a
banner naming any file over `MAX_SAVED_BYTES`, which isn't saved, with the
cell that stores it as an asset instead, and the open notebook when it didn't
hydrate, since nothing typed into the blank is saved.

Reserved paths the proxy handles itself instead of forwarding:

- `GET /__sg__/dashboard` — 302 to the owner's dashboard
  (`STARGAZER_ADMIN_URL`), so notebooks can link back with a stable relative
  path.
- `GET /__sg__/save-status` — the files in `/workspace` over `MAX_SAVED_BYTES`
  and the notebook that didn't hydrate, which aren't saved; the injected
  banner polls it.
- `GET /__sg__/ready` — 200 once local marimo answers, 503 while it's still
  cold-starting.
- `WS  /__sg__/agent/<name>` — marimo's agent panel. Runs the agent's entry
  in `AGENT_COMMANDS`, which speaks the Agent Client Protocol on stdio, per
  connection and relays its stdio line by line, the framing marimo's `stdio-to-ws` uses. The
  child's environment is scrubbed of secret-shaped vars; that's tidiness,
  not a boundary.

While marimo is still starting, a browser request gets a small self-refreshing
"Starting your notebook…" page instead of an error.

It is a top-level module, not under `app/`, because a hosted pod's code
bundle unpacks the dashboard's `app/` package into the pod's `/home/flyte`
cwd, which would shadow it.

spec: [docs/architecture/runtime.md](../docs/architecture/runtime.md)
"""

import asyncio
import os
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
# The pod-local dir the launch hydrates into, where the dashboard points
# notebook paths.
WORKSPACE_DIR = Path("/workspace")
# Never saved: Python's bytecode caches and marimo's per-notebook session caches.
_SKIPPED_DIRS = {"__pycache__", "__marimo__"}
# A file over this isn't saved with the workspace: big data belongs in the asset
# store, and the save at SIGTERM has to fit in the pod's grace period. The same
# limit as an upload through the dashboard's asset browser.
MAX_SAVED_BYTES = 100 * 1024**2

# Env keys never handed to the agent. The suffix list catches future
# secret-shaped vars without an explicit entry per name. The org's Pinata key is
# in the notebook's env on purpose, but kept from the agent, where its `env`
# would put it in the agent's context. marimo's terminal inherits marimo's env
# whole, so this is tidiness, not a boundary.
_AGENT_SECRET_KEYS = {"PINATA_JWT"}
_AGENT_SECRET_SUFFIXES = ("_SECRET", "_TOKEN", "_JWT", "_KEY", "_PASSWORD")

# The agents marimo's panel can start, each speaking the Agent Client Protocol
# on stdio, one process per panel connection, installed on PATH by the image
# (runtime/Dockerfile). The names are marimo's.
AGENT_COMMANDS = {
    "claude": ["claude-agent-acp"],
    "opencode": ["opencode", "acp"],
}
# A protocol message is one line, and a file the agent reads or writes rides
# in one: well past asyncio's 64 KiB default line limit.
_AGENT_LINE_LIMIT = 64 * 1024**2

# Request headers that never reach marimo: the platform session cookies and the
# identity headers it injects (notably `X-User-Token`, the visitor's ID token).
_STRIPPED_PREFIXES = ("x-user-",)
_STRIPPED_HEADERS = {"host", "cookie"}

# The script pointing marimo's agent panel at `/__sg__/agent/`, spliced into
# every marimo HTML page before </body>. Kept as a static asset
# (agent_redirect.html) so it gets real HTML/JS tooling instead of living as a
# Python string. Read once at import. In the image it's baked next to this
# module (runtime/Dockerfile), so resolving it relative to __file__ works both
# in-repo and in-pod.
_AGENT_REDIRECT_INJECTION = (Path(__file__).parent / "agent_redirect.html").read_bytes()
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

# Where the agents keep a sign-in, relative to the home directory: Claude
# Code's credentials and its account state, which it asks to set up again
# without, and OpenCode's credentials. Nothing else in the home directory is
# kept.
AGENT_SIGN_INS = (
    ".claude/.credentials.json",
    ".claude.json",
    ".local/share/opencode/auth.json",
)

# Relative path -> (size, mtime) of each file as it was last stored. Seeded at
# proxy startup from the freshly hydrated disk, so nothing re-uploads needlessly,
# and the set of files a pass may delete from the store.
_synced: dict[str, tuple[int, int]] = {}

# The same for `AGENT_SIGN_INS`, relative to the home directory.
_sign_ins_synced: dict[str, tuple[int, int]] = {}

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
    """Async body of `hydrate()`."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    prefix = _user_prefix("workspace")
    if prefix is None:
        print("[sg] workspace store not configured; nothing to load")
        return
    _init_storage()
    n = await _download_prefix(prefix, WORKSPACE_DIR)
    print(f"[sg] hydrated {n} file(s)")
    home = Path.home()
    n = await _download_prefix(_user_prefix("agents"), home)
    for rel in AGENT_SIGN_INS:
        with suppress(FileNotFoundError):
            (home / rel).chmod(0o600)
    if n:
        print(f"[sg] restored {n} agent sign-in file(s)")


def hydrate() -> None:
    """Fill `/workspace` from the owner's stored workspace, and the home
    directory from their stored sign-ins.

    Run by the launch script, as its own process, before marimo starts, so the
    notebook marimo opens already exists on disk. Always leaves the dir in
    place, empty for a new user or an unconfigured store.
    """
    asyncio.run(hydrate_async())


def _seed_from_disk() -> None:
    """Record every file now in `/workspace` as already stored.

    Called by `lifespan` at proxy startup, after the launch script's
    `hydrate()` (a separate process), so the first pass doesn't re-upload what
    was just downloaded, and the same for the agents' sign-ins. It's also what a later pass may delete from the
    store: only files this pod knew about. After a failed
    hydrate the workspace is empty, so nothing stored is ever deleted.
    """
    for rel in AGENT_SIGN_INS:
        with suppress(FileNotFoundError):
            _sign_ins_synced.setdefault(rel, _stamp(Path.home() / rel))
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
    read at all, and nor is one over `MAX_SAVED_BYTES`. A file deleted from
    `/workspace` is deleted from the store, if this pod hydrated or saved it.
    One this pod hydrated or saved that's gone from the store was deleted
    elsewhere, by the dashboard's delete while the pod was still up, and
    isn't put back: the pass after the delete would otherwise undo it,
    whenever the file changed since the last pass (marimo rewrites a notebook
    as it opens). Nor is the pod's notebook when it didn't hydrate
    (`SG_UNSAVED_NOTEBOOK`, set by the launch script): the blank marimo opens
    in its place would undo the delete, or, after a failed hydrate, overwrite
    the stored notebook. A failed upload or delete is logged and retried on
    the next pass rather than raised.
    """
    prefix = _user_prefix("workspace")
    if prefix is None or not WORKSPACE_DIR.is_dir():
        return []
    _init_storage()
    files = _workspace_files()
    unsaved = os.environ.get("SG_UNSAVED_NOTEBOOK")
    saved = []
    for rel, path in sorted(files.items()):
        try:
            stamp = _stamp(path)
            if (
                rel == unsaved
                or _synced.get(rel) == stamp
                or stamp[0] > MAX_SAVED_BYTES
            ):
                continue
            uri = f"{prefix}/{rel}"
            if rel in _synced and not await flyte.storage.exists(uri):
                _synced[rel] = stamp
                continue
            await _upload(uri, path.read_bytes())
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


async def save_sign_ins() -> list[str]:
    """Save each agent sign-in that changed; return what was saved or deleted.

    One whose size and modification time match what was last stored isn't
    read. One this pod restored or saved that's gone from the home directory
    was signed out of, and is deleted from the store. A failed upload or
    delete is logged and retried on the next pass rather than raised.
    """
    prefix = _user_prefix("agents")
    if prefix is None:
        return []
    _init_storage()
    changed = []
    for rel in AGENT_SIGN_INS:
        path = Path.home() / rel
        try:
            if not path.is_file():
                if rel in _sign_ins_synced:
                    await asyncio.to_thread(_delete_sync, f"{prefix}/{rel}")
                    del _sign_ins_synced[rel]
                    changed.append(rel)
                continue
            stamp = _stamp(path)
            if _sign_ins_synced.get(rel) == stamp:
                continue
            await _upload(f"{prefix}/{rel}", path.read_bytes())
        except Exception as exc:
            print(f"[sg] saving sign-in {rel} failed: {exc}")
            continue
        _sign_ins_synced[rel] = stamp
        changed.append(rel)
    if changed:
        print(f"[sg] saved sign-ins {', '.join(changed)}")
    return changed


def _save_interval() -> float:
    """Seconds between save passes, from the pod's env; 0 means none.

    The dashboard sets it at launch from the owner's settings, 30 unless they
    changed it. The pass reads only files whose size or mtime changed, so a
    short interval costs little and bounds what a pod that dies without
    SIGTERM loses.
    """
    return float(os.environ.get("SG_SAVE_INTERVAL_SECONDS", "30"))


async def _sync_loop(interval: float) -> None:
    """Save every `interval` seconds for the life of the pod."""
    while True:
        await asyncio.sleep(interval)
        try:
            await sync_once()
            await save_sign_ins()
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
    receives SIGTERM and runs this hook. See runtime/launch-notebook.sh — an
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
        await save_sign_ins()
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
    """What the pod won't save, for the injected banner.

    `unsaved` is the files in `/workspace` too big to save, read from disk on
    each request rather than from the last save pass, so the banner works
    with the periodic save turned off too. `not_loaded` is the open notebook
    when it didn't hydrate (`SG_UNSAVED_NOTEBOOK`), else `None`.
    """
    unsaved = []
    if WORKSPACE_DIR.is_dir():
        for rel, path in sorted(_workspace_files().items()):
            with suppress(FileNotFoundError):
                size = path.stat().st_size
                if size > MAX_SAVED_BYTES:
                    unsaved.append({"path": rel, "bytes": size})
    return {
        "limit_bytes": MAX_SAVED_BYTES,
        "unsaved": unsaved,
        "not_loaded": os.environ.get("SG_UNSAVED_NOTEBOOK"),
    }


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


def _agent_env() -> dict[str, str]:
    """Pod env with auth-critical secrets stripped, for the agent.

    Drops every key in `_AGENT_SECRET_KEYS` plus anything ending in a
    secret-shaped suffix, so credentials stay out of casual `env` output. Not a
    boundary (see the module docstring).
    """
    return {
        k: v
        for k, v in os.environ.items()
        if k not in _AGENT_SECRET_KEYS and not k.endswith(_AGENT_SECRET_SUFFIXES)
    }


@asgi_app.websocket("/__sg__/agent/{name}")
async def agent_bridge(websocket: WebSocket, name: str) -> None:
    """Bridge marimo's agent panel to an agent process over its stdio.

    Starts `name`'s entry in `AGENT_COMMANDS`, refusing any other name with
    1008, with a secret-scrubbed environment (`_agent_env`)
    in the pod's working directory, `/workspace`. Each frame from the panel,
    text or binary, is written to the agent's stdin as one line, and each line
    the agent prints is sent back as one text frame. Its stderr goes to the pod's log. The
    agent is killed when the panel disconnects, and the panel is disconnected
    when the agent exits.
    """
    if (command := AGENT_COMMANDS.get(name)) is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    agent = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        env=_agent_env(),
        limit=_AGENT_LINE_LIMIT,
    )

    async def agent_to_panel() -> None:
        """Send each line the agent prints to the panel until it exits."""
        async for line in agent.stdout:
            if line := line.rstrip(b"\r\n"):
                await websocket.send_text(line.decode())

    async def panel_to_agent() -> None:
        """Write each frame from the panel to the agent until it disconnects."""
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                return
            # marimo sends each message as a binary frame.
            if (data := msg.get("bytes")) is None:
                data = msg.get("text", "").encode()
            agent.stdin.write(data.rstrip(b"\r\n") + b"\n")
            await agent.stdin.drain()

    tasks = {
        asyncio.create_task(agent_to_panel()),
        asyncio.create_task(panel_to_agent()),
    }
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        if agent.returncode is None:
            agent.kill()
        await agent.wait()
        with suppress(RuntimeError):
            await websocket.close()


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
    the agent redirect and the save banner are spliced in before `</body>`
    (on every page, no marimo plugin needed). Everything else — static bundles, API
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
        # Buffer + splice the fragments. `aread()` decodes any
        # content-encoding, and the injection changes the size, so drop both
        # headers and let Starlette recompute the length.
        content = await resp.aread()
        await resp.aclose()
        content = content.replace(
            b"</body>",
            _AGENT_REDIRECT_INJECTION + _SAVE_BANNER_INJECTION + b"</body>",
            1,
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
