"""
### Reverse proxy in front of marimo, which also holds the notebook's volume.

Standalone ASGI app baked into the Stargazer image as the top-level module
`/usr/local/lib/sg_proxy.py`, beside its HTML fragment. It imports no
stargazer code: it runs in the image's runtime venv (the project's `runtime`
group), with the `flyte` SDK for storage and `flyteplugins-union` for volumes.
Listens on the per-notebook pod's public port (8080) and forwards HTTP +
websocket traffic to marimo on `127.0.0.1:8081`.

**Auth.** The pod runs behind the platform login (`requires_auth=True`), but
it also answers at an in-cluster address that skips the login, where any pod
in any project can send whatever headers it likes (measured 2026-10-18). So on
Union (`SG_AUTH_ISSUER` set) `_TokenGate` checks every HTTP and websocket
request for a token the issuer signed, `X-User-Token`, whose subject is the
owner (`SG_OWNER_SUBJECT`) or one of `SG_ADMIN_SUBJECTS`: 401 without one, 403
for anyone else. The dashboard checks its own requests the same way.
`SG_OWNER_SUBJECT` also keys where the pod keeps the agents' sign-ins.
Platform cookies and `X-User-*` headers are stripped before anything reaches
marimo, so notebook code never sees the visitor's platform token through a
request.

**Workspace.** A workspace notebook is its own volume, mounted at the
notebook's folder, `/workspace/<slug>`, the directory of `SG_NOTEBOOK_PATH`.
`SG_NOTEBOOK_MANIFEST` is the URI of the notebook's manifest,
`{"locator", "file", "source"}`: the latest version's locator, the notebook's
file name and that file's text in that version (the pod contract in the runtime
doc has the layout). `lifespan` mounts at startup, since the process that
mounts is the one that commits, and the launch script starts marimo once the
notebook's file shows up in the mount. In edit mode the pod forks the latest
version and mounts the fork read-write. Every `SG_SAVE_INTERVAL_SECONDS` (30
by default, 0 for only at shutdown) a file under the mount that changed since
the last commit is committed as a new version and the manifest is written to
name it; shutdown finalizes the volume, which commits and unmounts, or, when
nothing changed since the last commit, abandons it, so a session that only
looked at the notebook adds no version. In run mode the pod mounts a throwaway
fork of the latest version read-write, since the header fixes and marimo's own
session caches write beside the notebook: it never commits or writes the
manifest, and its edits are thrown away when the pod stops. With no
manifest (a built-in notebook, a local `docker run`) nothing is mounted.

The manifest write is conditional on the ETag the pod last read or wrote
(`If-Match`): the dashboard writes it too while no pod has the notebook, and
nothing else coordinates the two. A refused write means someone else wrote a
newer version. The pod then stops writing the manifest for the rest of its
life, logs each version it commits after that by locator, and the page carries
a banner saying its changes no longer reach the notebook. A commit or write
that fails for any other reason is logged and tried again on the next pass.

**Sign-ins.** The agents' sign-ins (`AGENT_SIGN_INS`, in the home directory)
are per user, shared by all of a user's pods, so they're kept under
`<STARGAZER_WORKSPACE_ROOT>/users/<subject>/agents/`: put back at launch by
`restore_sign_ins()`, readable by the owner alone, saved by the same passes as
the volume when they change, and deleted from the store on a sign-out.

**Agents.** The terminal and the agents are marimo's own. marimo's agent panel
dials each agent at a fixed port on the page's host, which a hosted pod
doesn't serve, so every `text/html` response gets a script spliced in before
`</body>` (`sockets.html`) that points Claude Code's and OpenCode's at
`/__sg__/agent/<name>` below. The proxy changes into the notebook's folder
once it's mounted, so the agents start there.
**Long-lived sockets.** The platform cuts every request to the pod at its
request timeout, websockets included: the editor's session, the terminal and
the agent panel's would close every few minutes. Only the browser's leg is
cut, so the proxy keeps each socket's upstream (marimo's socket, an agent's
stdio) in a `_Channel`, apart from the browser connection carrying it, and the
same script hands each socket over to a successor connection before the cut.
A connection names its channel with `__sg_rid`; one that also passes
`__sg_resume=<n>` takes the channel over once the proxy has received the `n`
frames the page sent on the old connection, which is then closed with 4000.
A channel ends when its connection does with no successor waiting, so a
connection the network drops still closes as it did. A connection naming no
channel is relayed on its own.

Reserved paths the proxy handles itself instead of forwarding:

- `GET /__sg__/dashboard` — 302 to the owner's dashboard
  (`STARGAZER_ADMIN_URL`), so notebooks can link back with a stable relative
  path.
- `GET /__sg__/ready` — 200 once local marimo answers, 503 while it's still
  cold-starting.
- `WS  /__sg__/agent/<name>` — marimo's agent panel. Runs the agent's entry
  in `AGENT_COMMANDS`, which speaks the Agent Client Protocol on stdio, per
  connection and relays its stdio line by line, the framing marimo's `stdio-to-ws` uses. The
  child's environment is scrubbed of secret-shaped vars; that's tidiness,
  not a boundary. Each session the panel opens gets the pod's `stargazer`
  MCP server (`STARGAZER_MCP_SERVER`) beside the panel's own servers.

While marimo is still starting, a browser request gets a small self-refreshing
"Starting your notebook…" page instead of an error.

It is a top-level module, not under `app/`, because a hosted pod's code
bundle unpacks the dashboard's `app/` package into the pod's `/home/flyte`
cwd, which would shadow it.

spec: [docs/architecture/runtime.md](../docs/architecture/runtime.md)
"""

import asyncio
import json
import os
import sys
import tomllib
from contextlib import asynccontextmanager, suppress
from functools import cache
from pathlib import Path

import flyte
import flyte.storage
import httpx
import jwt
import obstore
import websockets
from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from obstore.exceptions import PreconditionError
from starlette.background import BackgroundTask
from starlette.websockets import WebSocketDisconnect

MARIMO_HOST = "127.0.0.1"
MARIMO_HTTP_PORT = 8081
# Not counted as a change to a notebook's volume: Python's bytecode caches and
# marimo's per-notebook session caches.
_SKIPPED_DIRS = {"__pycache__", "__marimo__"}

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
# The pod's `stargazer` MCP server, at `stargazer --http`'s default address,
# which the launch script starts in edit mode with the pod's whole env. marimo
# opens every session with no MCP servers, so the bridge adds this one to each
# request that lists them (`session/new`, `session/load`, ...), in the
# protocol's own shape; both agents take HTTP servers.
STARGAZER_MCP_SERVER = {
    "type": "http",
    "name": "stargazer",
    "url": "http://127.0.0.1:8000/mcp",
    "headers": [],
}
# A protocol message is one line, and a file the agent reads or writes rides
# in one: well past asyncio's 64 KiB default line limit.
_AGENT_LINE_LIMIT = 64 * 1024**2

# The query parameters the page script adds to a socket: the channel it names,
# and on a successor, how many frames the page sent on the connection it takes
# over. They're the proxy's, never passed on to marimo.
_CHANNEL_PARAM = "__sg_rid"
_RESUME_PARAM = "__sg_resume"
# How long a successor waits for the old connection's last frames before it's
# refused (4409), leaving the old connection in place.
_HANDOVER_SECONDS = 10

# Request headers that never reach marimo: the platform session cookies and the
# identity headers it injects (notably `X-User-Token`, the visitor's ID token).
_STRIPPED_PREFIXES = ("x-user-",)
_STRIPPED_HEADERS = {"host", "cookie"}

# The script that points marimo's agent panel at `/__sg__/agent/` and hands the
# page's sockets over before the platform cuts them, spliced into every marimo
# HTML page before </body>. Kept as a static asset (sockets.html) so it gets
# real HTML/JS tooling instead of living as a Python string. Read once at
# import. In the image it's baked next to this module (runtime/Dockerfile), so
# resolving it relative to __file__ works both in-repo and in-pod.
_SOCKETS_INJECTION = (Path(__file__).parent / "sockets.html").read_bytes()

# Spliced into every page once the manifest has refused a write, so a user who
# is still typing sees that it no longer saves. A fixed fragment: the proxy
# fills nothing into it.
_REFUSED_BANNER = (
    b'<div style="position:fixed;bottom:0;left:0;right:0;z-index:2147483647;'
    b"padding:8px 16px;background:#b3261e;color:#fff;font:14px system-ui,sans-serif;"
    b'text-align:center">This notebook was changed from somewhere else. '
    b"Changes made here no longer save to it: copy what you need, then reopen "
    b"the notebook.</div>"
)


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

# Relative path -> (size, mtime) of each of `AGENT_SIGN_INS` as it was last
# stored, relative to the home directory. Seeded at proxy startup from what
# `restore_sign_ins()` put back, so nothing re-uploads needlessly.
_sign_ins_synced: dict[str, tuple[int, int]] = {}

_storage_ready = False

# The notebook volume this pod holds, once `lifespan` has mounted it.
_notebook: _NotebookVolume | None = None


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
# Agent sign-ins: per user, in the workspace store
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


async def restore_sign_ins_async() -> None:
    """Async body of `restore_sign_ins()`."""
    prefix = _user_prefix("agents")
    if prefix is None:
        print("[sg] workspace store not configured; no agent sign-ins to restore")
        return
    _init_storage()
    home = Path.home()
    n = await _download_prefix(prefix, home)
    for rel in AGENT_SIGN_INS:
        with suppress(FileNotFoundError):
            (home / rel).chmod(0o600)
    if n:
        print(f"[sg] restored {n} agent sign-in file(s)")


def restore_sign_ins() -> None:
    """Put the owner's stored agent sign-ins back in the home directory.

    Run by the launch script, as its own process, before marimo starts. A new
    user, or a deploy without a store, restores none.
    """
    asyncio.run(restore_sign_ins_async())


def _script_header(lines: list[str]) -> tuple[int, int, dict] | None:
    """Find a notebook's PEP 723 header: its opening and closing line indexes
    and its parsed TOML, or None when it has none, it's unclosed or it doesn't
    parse.
    """
    start = next(
        (i for i, line in enumerate(lines) if line.rstrip("\r\n") == "# /// script"),
        None,
    )
    if start is None:
        return None
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].rstrip("\r\n") == "# ///"),
        None,
    )
    if end is None:
        return None
    content = "".join(
        line[2:] if line.startswith("# ") else line.removeprefix("#")
        for line in lines[start + 1 : end]
    )
    try:
        return start, end, tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return None


def _add_to_table(
    lines: list[str], start: int, end: int, table: str, entry: str
) -> None:
    """Put `entry` first in the header's `[table]`, adding the table before the
    header's close when it has none.
    """
    found = next(
        (i for i in range(start + 1, end) if lines[i].rstrip("\r\n") == f"# [{table}]"),
        None,
    )
    if found is not None:
        lines.insert(found + 1, entry)
    else:
        lines[end:end] = ["#\n", f"# [{table}]\n", entry]


def pin_python(notebook: str | Path) -> None:
    """Pin a notebook header's Python to the image's own minor version.

    pixi's sandbox takes conda-forge's newest Python for a header that doesn't
    pin one, which marimo's own packages may not support yet, so the kernel
    never starts. The launch script runs this before marimo. Headers written
    before the pixi sandbox and notebooks from elsewhere have no pin.
    """
    path = Path(notebook)
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", newline="")
    lines = text.splitlines(keepends=True)
    pin = f'# python = "{sys.version_info.major}.{sys.version_info.minor}.*"\n'
    if not any(line.rstrip("\r\n") == "# /// script" for line in lines):
        path.write_text(
            "# /// script\n# [tool.pixi.dependencies]\n" + pin + "# ///\n" + text,
            encoding="utf-8",
            newline="",
        )
        return
    found = _script_header(lines)
    if found is None:
        return
    start, end, parsed = found
    if "python" in parsed.get("tool", {}).get("pixi", {}).get("dependencies", {}):
        return
    _add_to_table(lines, start, end, "tool.pixi.dependencies", pin)
    path.write_text("".join(lines), encoding="utf-8", newline="")


def use_image_sdk(notebook: str | Path) -> None:
    """Copy a header's `[tool.uv.sources]` path for `stargazer-bio` to
    `[tool.pixi.pypi-dependencies]`.

    Headers saved before the pixi sandbox point `stargazer-bio` at the image's
    SDK in `[tool.uv.sources]`, which pixi doesn't read, so such a notebook's
    kernel would install the SDK from PyPI instead. The launch script runs this
    before marimo.
    """
    path = Path(notebook)
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8", newline="").splitlines(keepends=True)
    found = _script_header(lines)
    if found is None:
        return
    start, end, parsed = found
    tool = parsed.get("tool", {})
    source = tool.get("uv", {}).get("sources", {}).get("stargazer-bio")
    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
        return
    if "stargazer-bio" in tool.get("pixi", {}).get("pypi-dependencies", {}):
        return
    entry = f"# stargazer-bio = {{ path = {json.dumps(source['path'])} }}\n"
    _add_to_table(lines, start, end, "tool.pixi.pypi-dependencies", entry)
    path.write_text("".join(lines), encoding="utf-8", newline="")


def _seed_from_disk() -> None:
    """Record each agent sign-in now in the home directory as already stored.

    Called by `lifespan` at proxy startup, after the launch script's
    `restore_sign_ins()` (a separate process), so the first pass doesn't
    re-upload what was just downloaded. It's also what a later pass may delete
    from the store: only sign-ins this pod knew about.
    """
    for rel in AGENT_SIGN_INS:
        with suppress(FileNotFoundError):
            _sign_ins_synced.setdefault(rel, _stamp(Path.home() / rel))


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


# ---------------------------------------------------------------------------
# The notebook's volume
# ---------------------------------------------------------------------------


def _manifest_target(uri: str):
    """The object store and key of the manifest at `uri`, with the pod's own
    credentials.

    Flyte's own obstore bypass builds its store the same way; the manifest's
    conditional writes need the store itself, which `flyte.storage` doesn't
    wrap.
    """
    _init_storage()
    fs = flyte.storage.get_underlying_filesystem(path=uri)
    bucket, key = fs._split_path(uri)
    return fs._construct_store(bucket), key


def _volume_stamp(folder: Path) -> dict[str, tuple[int, int]]:
    """Every file under `folder` that counts as a change: its path relative to
    `folder` -> size and modification time.

    Skips `_SKIPPED_DIRS`. Symlinks aren't followed.
    """
    files = {}
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in _SKIPPED_DIRS]
        for name in names:
            path = Path(root) / name
            if not path.is_symlink():
                with suppress(FileNotFoundError):
                    files[path.relative_to(folder).as_posix()] = _stamp(path)
    return files


class _NotebookVolume:
    """A workspace notebook's volume, mounted in this pod, and its manifest.

    `store` and `key` are the manifest's object. Built by `open()`, which
    reads the manifest and mounts; in edit mode `save()` commits and writes
    the manifest, and its final pass finalizes the volume or abandons it when
    nothing changed. In run mode the mount is a throwaway fork: `save()`
    commits nothing and its final pass abandons it, so nothing it holds
    outlives the pod.
    """

    def __init__(self, store, key: str, folder: Path, edit: bool) -> None:
        """A volume for the manifest at `key` in `store`, to mount at `folder`."""
        self.store = store
        self.key = key
        self.folder = folder
        self.edit = edit
        self.file = ""
        self.etag = ""
        self.volume = None
        self.stamp: dict[str, tuple[int, int]] = {}
        # The version committed but not yet named by the manifest, with the
        # notebook's text in it, which can't be read after the unmount.
        self.pending: tuple[str, str] | None = None
        self.refused = False

    async def open(self) -> None:
        """Read the manifest and mount the latest version at `folder`.

        Both modes mount a fork of it read-write, named like the volume it
        branches from, so the fork stays under the same prefix. Run mode's is
        never committed: the header fixes and marimo's session caches write
        beside the notebook, which a read-only mount would refuse.
        """
        from flyteplugins.union.io import ROVolume

        result = await obstore.get_async(self.store, self.key)
        self.etag = result.meta["e_tag"]
        manifest = json.loads(bytes(await result.bytes_async()))
        self.file = manifest["file"]
        latest = await ROVolume.from_locator(manifest["locator"])
        self.volume = await latest.fork(latest.name)
        await self.volume.mount(mount_path=str(self.folder))
        self.stamp = _volume_stamp(self.folder)
        print(f"[sg] mounted {self.volume.name} at {self.folder}")

    def _source(self) -> str:
        """The notebook's text now, empty if the file is gone."""
        with suppress(FileNotFoundError):
            return (self.folder / self.file).read_text(encoding="utf-8")
        return ""

    async def save(self, *, final: bool = False) -> None:
        """Commit what changed since the last commit, and write the manifest.

        `final` ends the volume instead, for the pod's last pass: finalized
        (commit and unmount) when files changed since the last commit, else
        abandoned (released without a commit), so a session that changed
        nothing adds no version. Run mode's last pass abandons its throwaway
        fork and nothing else happens there. A manifest write that failed is
        tried again here before anything new is committed.
        """
        if not self.edit:
            if final:
                await self.volume.abandon()
            return
        stamp = _volume_stamp(self.folder)
        changed = stamp != self.stamp
        if final and not changed and self.pending is None:
            await self.volume.abandon()
            return
        if changed or final:
            source = self._source()
            if final:
                version = await self.volume.finalize(message="shutdown")
            else:
                version = await self.volume.commit(message="autosave")
            if changed:
                self.stamp = stamp
                self.pending = (version.locator, source)
        if self.pending is not None:
            await self._write_manifest(*self.pending)

    async def _write_manifest(self, locator: str, source: str) -> None:
        """Name `locator` as the latest version, if nobody else has written since
        this pod last did.

        After a refusal it only logs the version, so every one the pod commits
        stays findable.
        """
        if self.refused:
            print(f"[sg] notebook version not named in its manifest: {locator}")
            self.pending = None
            return
        body = json.dumps({"locator": locator, "file": self.file, "source": source})
        try:
            result = await obstore.put_async(
                self.store, self.key, body.encode(), mode={"e_tag": self.etag}
            )
        except PreconditionError:
            self.refused = True
            self.pending = None
            print(
                "[sg] ERROR: the notebook was changed somewhere else while this pod "
                f"had it; this pod's changes are kept as version {locator} and "
                "no longer named in the notebook's manifest"
            )
            return
        self.etag = result["e_tag"]
        self.pending = None
        print(f"[sg] saved notebook version {locator}")


async def _open_notebook() -> _NotebookVolume | None:
    """Mount the notebook's volume when the pod has a manifest to read.

    The launch script exports `SG_NOTEBOOK_MANIFEST`, `SG_NOTEBOOK_PATH` and
    `SG_NOTEBOOK_MODE`; without a manifest (a built-in notebook, a local run)
    nothing is mounted. A failure to mount stops the pod, since marimo would
    have nothing to open. Changes into the folder afterwards: the agents start
    in the proxy's working directory.
    """
    uri = os.environ.get("SG_NOTEBOOK_MANIFEST")
    if not uri:
        return None
    folder = Path(os.environ["SG_NOTEBOOK_PATH"]).parent
    store, key = _manifest_target(uri)
    notebook = _NotebookVolume(
        store, key, folder, edit=os.environ.get("SG_NOTEBOOK_MODE") == "edit"
    )
    await notebook.open()
    os.chdir(folder)
    return notebook


def _save_interval() -> float:
    """Seconds between save passes, from the pod's env; 0 means none.

    The dashboard sets it at launch from the owner's settings, 30 unless they
    changed it. A pass commits only when a file changed, so a short interval
    costs little and bounds what a pod that dies without SIGTERM loses.
    """
    return float(os.environ.get("SG_SAVE_INTERVAL_SECONDS", "30"))


async def _save_pass(*, final: bool = False) -> None:
    """One save: the notebook's volume, then the agents' sign-ins.

    Each is tried on its own, so a failure in one is logged and never keeps the
    other from saving or stops the pod.
    """
    try:
        if _notebook is not None:
            await _notebook.save(final=final)
    except Exception as exc:
        print(f"[sg] saving the notebook failed: {exc}")
    try:
        await save_sign_ins()
    except Exception as exc:
        print(f"[sg] saving sign-ins failed: {exc}")


async def _save_loop(interval: float) -> None:
    """Save every `interval` seconds for the life of the pod."""
    while True:
        await asyncio.sleep(interval)
        await _save_pass()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Mount the notebook's volume, run the save loop while serving, and save
    once more on shutdown.

    Nothing in the pod outlives it but the volume's versions and the sign-ins,
    so a change not committed before the pod idles is lost. With the interval
    at 0 there's no loop, and this last pass is the only save. Flyte's `fserve`
    wrapper is PID 1 and forwards the Knative SIGTERM to its one direct child;
    the launch script's `exec` chain (args prepend `exec`, then the script
    `exec`s uvicorn) makes uvicorn that direct child, so it receives SIGTERM
    and runs this hook. See runtime/launch-notebook.sh — an intermediate shell
    anywhere in that chain would swallow the signal and skip it.
    """
    global _notebook
    _seed_from_disk()
    _notebook = await _open_notebook()
    interval = _save_interval()
    loop_task = asyncio.create_task(_save_loop(interval)) if interval > 0 else None
    yield
    if loop_task is not None:
        loop_task.cancel()
        with suppress(asyncio.CancelledError):
            await loop_task
    await _save_pass(final=True)
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


def _with_stargazer_mcp(message: bytes) -> bytes:
    """Add `STARGAZER_MCP_SERVER` to a panel request that lists MCP servers.

    Any other message, including one that only mentions `mcpServers` in its
    text, passes through byte for byte. The substring check keeps the large
    messages (file contents the agent asked the panel to read) from being
    parsed.
    """
    if b'"mcpServers"' not in message:
        return message
    request = json.loads(message)
    servers = (request.get("params") or {}).get("mcpServers")
    if "method" not in request or not isinstance(servers, list):
        return message
    servers.append(STARGAZER_MCP_SERVER)
    return json.dumps(request).encode()


class _AgentUpstream:
    """An agent process's stdio as a channel's upstream: one line per frame."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        """Wrap a started agent process."""
        self.process = process

    async def send(self, data: str | bytes) -> None:
        """Write a frame from the panel to the agent's stdin as one line.

        The pod's MCP server is added to the session requests
        (`_with_stargazer_mcp`).
        """
        if isinstance(data, str):
            data = data.encode()
        self.process.stdin.write(_with_stargazer_mcp(data.rstrip(b"\r\n")) + b"\n")
        await self.process.stdin.drain()

    async def _lines(self):
        """Each non-empty line the agent prints, until it exits."""
        async for line in self.process.stdout:
            if line := line.rstrip(b"\r\n"):
                yield line.decode()

    def __aiter__(self):
        """Iterate the agent's output lines as text frames."""
        return self._lines()

    async def close(self) -> None:
        """Kill the agent if it's still running, and reap it."""
        if self.process.returncode is None:
            self.process.kill()
        await self.process.wait()


# The channels open now, by the name the page gave them (`_CHANNEL_PARAM`).
_channels: dict[str, _Channel] = {}


class _Channel:
    """One upstream, carried by a browser connection and then its successors.

    The upstream is anything with `send(frame)`, async iteration over its
    frames and `close()`: marimo's socket or an `_AgentUpstream`. Frames from
    the upstream go to the connection carrying the channel, under `_lock`, so a
    handover never splits one. The channel ends, closing its upstream and its
    connection, when the upstream ends, or when its connection does with no
    successor waiting.
    """

    def __init__(self, name: str | None, upstream) -> None:
        """A channel for `upstream`, registered under `name` if it has one."""
        self.name = name
        self.upstream = upstream
        self.downstream: WebSocket | None = None
        # Frames received from the current connection, and whether it has
        # gone, which a waiting successor watches (`_changed`).
        self.received = 0
        self.downstream_gone = False
        self.successor_waiting = False
        self.closed = False
        self._changed = asyncio.Condition()
        self._lock = asyncio.Lock()
        self._pump: asyncio.Task | None = None
        if name:
            _channels[name] = self

    async def serve(self, websocket: WebSocket) -> None:
        """Carry the channel on its first connection, starting the upstream's relay."""
        self.downstream = websocket
        self._pump = asyncio.create_task(self._relay_upstream())
        await self._carry(websocket)

    async def take_over(self, websocket: WebSocket, sent: int) -> None:
        """Move the channel to `websocket` once the old connection's `sent` frames are in.

        Refused with 4404 when the channel has ended or a successor is already
        waiting, and with 4409 when the frames don't arrive within
        `_HANDOVER_SECONDS`, both leaving the old connection as it was. The old
        connection is closed with 4000 after the last frame sent on it.
        """
        if self.closed or self.successor_waiting:
            await websocket.close(code=4404)
            return
        self.successor_waiting = True
        try:
            async with self._changed:
                await asyncio.wait_for(
                    self._changed.wait_for(
                        lambda: (
                            self.closed or self.downstream_gone or self.received >= sent
                        )
                    ),
                    _HANDOVER_SECONDS,
                )
        except TimeoutError:
            self.successor_waiting = False
            await websocket.close(code=4409)
            if self.downstream_gone:
                await self.close()
            return
        if self.closed:
            await websocket.close(code=4404)
            return
        async with self._lock:
            old, self.downstream = self.downstream, websocket
            self.received = 0
            self.downstream_gone = False
            self.successor_waiting = False
            with suppress(RuntimeError, WebSocketDisconnect):
                await old.close(code=4000)
        await self._carry(websocket)

    async def _carry(self, websocket: WebSocket) -> None:
        """Relay `websocket`'s frames upstream until it disconnects.

        Then the channel ends, unless a successor has taken it over or is
        waiting to.
        """
        try:
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if (data := msg.get("text")) is None and (
                    data := msg.get("bytes")
                ) is None:
                    continue
                await self.upstream.send(data)
                async with self._changed:
                    self.received += 1
                    self._changed.notify_all()
        except Exception:
            pass
        if self.downstream is not websocket:
            return
        if self.successor_waiting:
            async with self._changed:
                self.downstream_gone = True
                self._changed.notify_all()
            return
        await self.close()

    async def _relay_upstream(self) -> None:
        """Send each upstream frame to the connection carrying the channel, then end it."""
        try:
            async for msg in self.upstream:
                async with self._lock:
                    with suppress(Exception):
                        if isinstance(msg, bytes):
                            await self.downstream.send_bytes(msg)
                        else:
                            await self.downstream.send_text(msg)
        except Exception:
            pass
        await self.close()

    async def close(self) -> None:
        """End the channel: close its upstream and its connection, wake a waiting successor."""
        if self.closed:
            return
        self.closed = True
        if self.name:
            _channels.pop(self.name, None)
        if self._pump is not None and self._pump is not asyncio.current_task():
            self._pump.cancel()
        with suppress(Exception):
            await self.upstream.close()
        with suppress(RuntimeError, WebSocketDisconnect):
            await self.downstream.close()
        async with self._changed:
            self._changed.notify_all()


async def _relay(websocket: WebSocket, open_upstream) -> None:
    """Carry `websocket` on a channel: a new one around `open_upstream()`, or the one it takes over."""
    name = websocket.query_params.get(_CHANNEL_PARAM)
    resume = websocket.query_params.get(_RESUME_PARAM)
    await websocket.accept()
    if name and resume is not None:
        if (channel := _channels.get(name)) is None:
            await websocket.close(code=4404)
            return
        await channel.take_over(websocket, int(resume))
        return
    await _Channel(name, await open_upstream()).serve(websocket)


@asgi_app.websocket("/__sg__/agent/{name}")
async def agent_bridge(websocket: WebSocket, name: str) -> None:
    """Bridge marimo's agent panel to an agent process over its stdio.

    Starts `name`'s entry in `AGENT_COMMANDS`, refusing any other name with
    1008, with a secret-scrubbed environment (`_agent_env`) in the pod's
    working directory, `/workspace`, as a channel's upstream (`_relay`), so a
    successor connection keeps the same process. Each frame from the panel,
    text or binary, is written to the agent's stdin as one line, with the pod's
    MCP server added to the session requests, and each line the agent prints is
    sent back as one text frame. Its stderr goes to the pod's log. The agent is
    killed when the panel disconnects with no successor, and the panel is
    disconnected when the agent exits.
    """
    if (command := AGENT_COMMANDS.get(name)) is None:
        await websocket.close(code=1008)
        return

    async def start() -> _AgentUpstream:
        """Start the agent process."""
        return _AgentUpstream(
            await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                env=_agent_env(),
                limit=_AGENT_LINE_LIMIT,
            )
        )

    await _relay(websocket, start)


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
    the sockets script, and the refused-write banner when it applies, are
    spliced in before `</body>` (on every page, no marimo plugin needed). Everything else — static bundles, API
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
        injection = _SOCKETS_INJECTION
        if _notebook is not None and _notebook.refused:
            injection += _REFUSED_BANNER
        content = content.replace(b"</body>", injection + b"</body>", 1)
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
    """Bridge a client websocket to marimo's websocket, as a channel's upstream (`_relay`).

    The upstream connection is opened without the client's headers, so no
    cookie or identity header reaches marimo here either, and without the
    channel's query parameters.
    """
    query = "&".join(
        part
        for part in websocket.url.query.split("&")
        if part and part.split("=", 1)[0] not in (_CHANNEL_PARAM, _RESUME_PARAM)
    )
    upstream_url = f"ws://{MARIMO_HOST}:{MARIMO_HTTP_PORT}/{path}"
    if query:
        upstream_url = f"{upstream_url}?{query}"

    async def connect():
        """Open marimo's socket."""
        return await websockets.connect(upstream_url)

    await _relay(websocket, connect)
