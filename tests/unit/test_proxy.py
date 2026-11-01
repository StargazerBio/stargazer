"""Tests for the notebook proxy (`runtime/proxy.py`).

The proxy is baked into the notebook image as a standalone module; here we
import it directly. Covered: what the proxy forwards from the platform-forwarded
`X-User-Subject`, the signed-token gate on Union, what is (not) forwarded to
marimo, the starting page while marimo is cold, the agent bridge, agent-redirect
and save-banner injection and streaming passthrough, and the workspace
hydrate/sync against a local store root through the real `flyte.storage`
calls. The upstream marimo server is faked with an
`httpx.MockTransport` installed as the proxy's shared upstream client.
"""

import asyncio
import json
import os
import sys
import time

import httpx
import pytest
from conftest import load_proxy
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

proxy = load_proxy()

OWNER = "387300641116005877"
OTHER = "111111111111111111"


@pytest.fixture(autouse=True)
def _owner(monkeypatch):
    """Every test runs in a pod owned by OWNER unless it says otherwise."""
    monkeypatch.setenv("SG_OWNER_SUBJECT", OWNER)


@pytest.fixture
def upstream(monkeypatch):
    """Fake the marimo upstream behind the proxy's shared client.

    Installs an `httpx.MockTransport`-backed client as `proxy._upstream` and
    returns a `configure(handler)` callable plus a recorder capturing the last
    upstream request (method, url, raw query, headers).
    """
    recorder: dict = {}

    def configure(respond):
        def handler(request: httpx.Request) -> httpx.Response:
            recorder["method"] = request.method
            recorder["url"] = str(request.url)
            recorder["query"] = request.url.query.decode()
            recorder["headers"] = {k.lower(): v for k, v in request.headers.items()}
            return respond(request)

        monkeypatch.setattr(
            proxy,
            "_upstream",
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        return recorder

    return configure


@pytest.fixture
def owner_client():
    """A TestClient (no lifespan) whose requests carry the owner's identity."""
    return TestClient(proxy.asgi_app, headers={"X-User-Subject": OWNER})


# ---------------------------------------------------------------------------
# Forwarding
# ---------------------------------------------------------------------------


def test_owner_request_reaches_marimo(owner_client, upstream):
    """The pod's owner is forwarded through to marimo."""
    recorder = upstream(lambda req: httpx.Response(200, text="hello"))

    resp = owner_client.get("/api/status")

    assert resp.status_code == 200
    assert resp.text == "hello"
    assert recorder["url"] == "http://127.0.0.1:8081/api/status"


def test_any_signed_in_visitor_reaches_marimo(upstream):
    """Off Union there's no token gate: any signed-in visitor is forwarded like the owner."""
    upstream(lambda req: httpx.Response(200, text="hello"))
    client = TestClient(proxy.asgi_app, headers={"X-User-Subject": OTHER})

    resp = client.get("/api/status")

    assert resp.status_code == 200
    assert resp.text == "hello"


@pytest.fixture
def on_union(monkeypatch, union_signer):
    """The pod runs on Union: every request needs a token the test signer made."""
    monkeypatch.setenv("SG_AUTH_ISSUER", union_signer.issuer)
    monkeypatch.setenv("SG_ADMIN_SUBJECTS", "")
    monkeypatch.setattr(proxy, "_signing_key", lambda token: union_signer.public_key)
    return union_signer


@pytest.mark.parametrize(
    ("who", "scheme", "expires_in", "status"),
    [
        pytest.param(None, None, 3600, 401, id="forged-headers-no-token"),
        pytest.param(OWNER, "IDToken", 3600, 200, id="owner"),
        pytest.param(OTHER, "Bearer", 3600, 200, id="admin"),
        pytest.param("333333333333333333", "IDToken", 3600, 403, id="stranger"),
        pytest.param(OWNER, "IDToken", -3600, 401, id="expired-owner"),
    ],
)
def test_on_union_only_a_valid_owner_or_admin_token_reaches_marimo(
    on_union, upstream, monkeypatch, who, scheme, expires_in, status
):
    """The owner's or a listed admin's browser carries a signed token through the
    login. A pod can reach the in-cluster address with an owner's headers but no
    token; a stranger's or an expired token doesn't get in either."""
    monkeypatch.setenv("SG_ADMIN_SUBJECTS", f"222222222222222222,{OTHER}")
    recorder = upstream(lambda req: httpx.Response(200, text="hello"))
    headers = {"X-User-Subject": OWNER}
    if who:
        headers["X-User-Token"] = f"{scheme} {on_union(who, expires_in=expires_in)}"

    resp = TestClient(proxy.asgi_app, headers=headers).get("/api/status")

    assert resp.status_code == status
    assert (recorder != {}) == (status == 200)


def test_on_union_the_agent_needs_a_token(on_union):
    """The agent websocket runs commands in the pod: forged headers don't open it."""
    client = TestClient(proxy.asgi_app, headers={"X-User-Subject": OWNER})

    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect("/__sg__/agent/claude"),
    ):
        pass
    assert exc.value.code == 1008


def test_identity_and_cookies_are_not_forwarded(owner_client, upstream):
    """Platform cookies and identity headers never reach notebook code."""
    recorder = upstream(lambda req: httpx.Response(200, text="ok"))

    owner_client.get(
        "/",
        headers={
            "Cookie": "flyte_at_1=secret-token",
            "X-User-Token": "IDToken abc",
            "X-User-Claim-Email": '"a@b.c"',
            "Accept": "text/plain",
        },
    )

    sent = recorder["headers"]
    assert "cookie" not in sent
    assert not [k for k in sent if k.startswith("x-user-")]
    assert sent["accept"] == "text/plain"


# ---------------------------------------------------------------------------
# Starting page while marimo is cold
# ---------------------------------------------------------------------------


def _refuse(request: httpx.Request) -> httpx.Response:
    """Mimic marimo not listening yet."""
    raise httpx.ConnectError("connection refused", request=request)


def test_html_request_gets_starting_page_while_marimo_is_cold(owner_client, upstream):
    """A browser hitting a cold pod sees a self-refreshing starting page."""
    upstream(_refuse)

    resp = owner_client.get("/", headers={"Accept": "text/html"})

    assert resp.status_code == 503
    assert "Starting your notebook" in resp.text
    assert 'http-equiv="refresh"' in resp.text


def test_non_html_request_gets_plain_503_while_marimo_is_cold(owner_client, upstream):
    """API calls against a cold pod get a plain 503, not the HTML page."""
    upstream(_refuse)

    resp = owner_client.get("/api/status", headers={"Accept": "application/json"})

    assert resp.status_code == 503
    assert "Starting your notebook" not in resp.text


# ---------------------------------------------------------------------------
# Agent bridge — stdio relay + secret scrub
# ---------------------------------------------------------------------------


def test_agent_env_scrubs_named_secrets(monkeypatch):
    """Named secrets stay out of the agent's environment."""
    monkeypatch.setenv("PINATA_JWT", "pinata-secret")
    monkeypatch.setenv("PINATA_GATEWAY", "https://dweb.link")  # not a secret

    env = proxy._agent_env()

    assert "PINATA_JWT" not in env
    assert env["PINATA_GATEWAY"] == "https://dweb.link"


def test_agent_env_scrubs_secret_shaped_suffixes(monkeypatch):
    """Future secret-shaped vars are dropped by suffix without an explicit entry."""
    monkeypatch.setenv("SOME_API_TOKEN", "x")
    monkeypatch.setenv("DB_PASSWORD", "x")
    monkeypatch.setenv("SIGNING_KEY", "x")
    monkeypatch.setenv("WEBHOOK_SECRET", "x")
    monkeypatch.setenv("THIRDPARTY_JWT", "x")
    monkeypatch.setenv("HARMLESS_VALUE", "keep")

    env = proxy._agent_env()

    for leaked in (
        "SOME_API_TOKEN",
        "DB_PASSWORD",
        "SIGNING_KEY",
        "WEBHOOK_SECRET",
        "THIRDPARTY_JWT",
    ):
        assert leaked not in env
    assert env["HARMLESS_VALUE"] == "keep"


# Stands in for `claude-agent-acp`: answers each line on stdin with one line
# naming what it got and whether it can see the Pinata key.
_FAKE_AGENT = """
import json, os, sys
for line in sys.stdin:
    print(json.dumps({"got": line.rstrip("\\n"), "pinata": os.environ.get("PINATA_JWT")}), flush=True)
"""


def test_agent_bridge_relays_lines_to_the_agent_process(owner_client, monkeypatch):
    """Each message, text or binary as marimo sends it, is a line on the agent's stdin; each stdout line is a message."""
    monkeypatch.setitem(
        proxy.AGENT_COMMANDS, "opencode", [sys.executable, "-c", _FAKE_AGENT]
    )
    monkeypatch.setenv("PINATA_JWT", "pinata-secret")

    with owner_client.websocket_connect("/__sg__/agent/opencode") as ws:
        ws.send_text('{"jsonrpc":"2.0","id":1,"method":"initialize"}')
        first = json.loads(ws.receive_text())
        ws.send_bytes(b'{"jsonrpc":"2.0","id":2}')
        second = json.loads(ws.receive_text())

    assert first == {
        "got": '{"jsonrpc":"2.0","id":1,"method":"initialize"}',
        "pinata": None,
    }
    assert second["got"] == '{"jsonrpc":"2.0","id":2}'


def test_agent_bridge_adds_the_stargazer_server_to_each_session(
    owner_client, monkeypatch
):
    """A session request reaches the agent with the pod's MCP server beside the panel's own."""
    monkeypatch.setitem(
        proxy.AGENT_COMMANDS, "claude", [sys.executable, "-c", _FAKE_AGENT]
    )
    theirs = {"name": "theirs", "command": "theirs-mcp", "args": [], "env": []}

    with owner_client.websocket_connect("/__sg__/agent/claude") as ws:
        ws.send_bytes(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "session/new",
                    "params": {"cwd": "/workspace", "mcpServers": []},
                }
            ).encode()
        )
        new = json.loads(json.loads(ws.receive_text())["got"])
        ws.send_bytes(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "session/load",
                    "params": {"sessionId": "s", "mcpServers": [theirs]},
                }
            ).encode()
        )
        load = json.loads(json.loads(ws.receive_text())["got"])

    stargazer = {
        "type": "http",
        "name": "stargazer",
        "url": "http://127.0.0.1:8000/mcp",
        "headers": [],
    }
    assert new["params"] == {"cwd": "/workspace", "mcpServers": [stargazer]}
    assert load["params"]["mcpServers"] == [theirs, stargazer]


def test_agent_bridge_refuses_an_agent_it_does_not_run(owner_client):
    """Only the agents the image installs can be started."""
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        owner_client.websocket_connect("/__sg__/agent/bash"),
    ):
        pass
    assert exc.value.code == 1008


def test_agent_bridge_closes_when_the_agent_exits(owner_client, monkeypatch):
    """An agent that dies takes the panel's connection with it."""
    monkeypatch.setitem(proxy.AGENT_COMMANDS, "claude", [sys.executable, "-c", "pass"])

    with (
        owner_client.websocket_connect("/__sg__/agent/claude") as ws,
        pytest.raises(WebSocketDisconnect),
    ):
        ws.receive_text()


# ---------------------------------------------------------------------------
# Forwarding path — HTML injection, streaming, query passthrough
# ---------------------------------------------------------------------------


def _serve_html(upstream):
    """Make marimo answer every request with a minimal HTML page."""
    upstream(
        lambda req: httpx.Response(
            200,
            content=b"<html><body><div id='app'></div></body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )


def test_proxy_injects_the_agent_redirect_and_banner_into_html(
    owner_client, upstream, monkeypatch, tmp_path
):
    """With a store, HTML gets the agent redirect and the save banner before </body>."""
    monkeypatch.setenv("STARGAZER_WORKSPACE_ROOT", str(tmp_path / "store"))
    _serve_html(upstream)

    resp = owner_client.get("/")

    assert resp.status_code == 200
    for injected in (b"/__sg__/agent/", b"sg-save-banner"):
        assert resp.content.index(injected) < resp.content.index(b"</body>")
    assert b"/__sg__/term" not in resp.content
    assert b"/__sg__/save-status" in resp.content


def test_proxy_leaves_the_banner_out_without_a_store(owner_client, upstream):
    """Without a store nothing is saved, so HTML gets the agent redirect but no banner."""
    _serve_html(upstream)

    resp = owner_client.get("/")

    assert resp.content.index(b"/__sg__/agent/") < resp.content.index(b"</body>")
    assert b"sg-save-banner" not in resp.content
    assert b"/__sg__/save-status" not in resp.content


def test_proxy_streams_non_html_untouched(owner_client, upstream):
    """Non-HTML bodies pass through byte-for-byte with their content type."""
    payload = bytes(range(256)) * 64
    upstream(
        lambda req: httpx.Response(
            200,
            content=payload,
            headers={"content-type": "application/octet-stream"},
        )
    )

    resp = owner_client.get("/assets/bundle.bin")

    assert resp.status_code == 200
    assert resp.content == payload


def test_proxy_preserves_raw_query_string(owner_client, upstream):
    """Duplicate query params reach marimo intact (no dict collapse)."""
    recorder = upstream(lambda req: httpx.Response(200, text="ok"))

    resp = owner_client.get("/api/kernel?file=a.py&tag=x&tag=y")

    assert resp.status_code == 200
    assert recorder["query"] == "file=a.py&tag=x&tag=y"


def test_proxy_forwards_method_and_body(owner_client, upstream):
    """POST bodies stream through to marimo with the method intact."""
    recorder = upstream(
        lambda req: httpx.Response(200, json={"echo": req.content.decode()})
    )

    resp = owner_client.post("/api/run", content=b'{"cell": 1}')

    assert recorder["method"] == "POST"
    assert resp.json() == {"echo": '{"cell": 1}'}


# ---------------------------------------------------------------------------
# Workspace hydrate + sync against a local store root
# ---------------------------------------------------------------------------


@pytest.fixture
def pod_dirs(tmp_path, monkeypatch):
    """Point the pod's workspace dir and the store root at tmp paths."""
    store = tmp_path / "store"
    monkeypatch.setenv("STARGAZER_WORKSPACE_ROOT", str(store))
    monkeypatch.setattr(proxy, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(proxy, "_synced", {})
    monkeypatch.setattr(proxy, "_sign_ins_synced", {})
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path / "workspace", store / "users" / OWNER / "workspace"


@pytest.fixture
def pod_home(pod_dirs, tmp_path):
    """The pod's home directory and where the owner's sign-ins are stored."""
    return tmp_path / "home", tmp_path / "store" / "users" / OWNER / "agents"


def test_hydrate_restores_every_file_at_its_path(pod_dirs):
    """Launch fills /workspace with every stored file, folders included."""
    workspace, stored = pod_dirs
    (stored / "data").mkdir(parents=True)
    (stored / "qc.py").write_text("# qc\n")
    (stored / "data" / "counts.csv").write_text("a,b\n")

    proxy.hydrate()

    assert (workspace / "qc.py").read_text() == "# qc\n"
    assert (workspace / "data" / "counts.csv").read_text() == "a,b\n"


def test_hydrate_new_user_gets_an_empty_dir(pod_dirs):
    """A user with nothing stored starts with an empty, existing directory."""
    workspace, _ = pod_dirs

    proxy.hydrate()

    assert sorted(p.name for p in workspace.iterdir()) == []


async def test_sync_saves_changed_files_at_their_paths(pod_dirs):
    """Unchanged hydrated files stay put; edits and new files of any kind save."""
    workspace, stored = pod_dirs
    stored.mkdir(parents=True)
    (stored / "qc.py").write_text("# qc\n")
    await proxy.hydrate_async()
    proxy._seed_from_disk()

    assert await proxy.sync_once() == []

    (workspace / "qc.py").write_text("# qc v2\n")
    (workspace / "data").mkdir()
    (workspace / "data" / "counts.csv").write_text("a,b\n")
    (workspace / "_scratch.py").write_text("# scratch\n")

    assert await proxy.sync_once() == ["_scratch.py", "data/counts.csv", "qc.py"]
    assert (stored / "qc.py").read_text() == "# qc v2\n"
    assert (stored / "data" / "counts.csv").read_text() == "a,b\n"
    assert await proxy.sync_once() == []


async def test_sync_skips_dotfiles_and_caches(pod_dirs):
    """Dotfiles, and Python's and marimo's caches, are never saved."""
    workspace, stored = pod_dirs
    for rel in (
        ".env",
        ".ipynb_checkpoints/a.py",
        "__marimo__/session/qc.py.json",
        "__pycache__/qc.cpython-313.pyc",
        "lib/__pycache__/helpers.cpython-313.pyc",
    ):
        (workspace / rel).parent.mkdir(parents=True, exist_ok=True)
        (workspace / rel).write_text("x")

    assert await proxy.sync_once() == []
    assert not stored.exists()


async def test_same_size_and_mtime_is_not_read(pod_dirs):
    """An edit that keeps a file's size and mtime goes unseen: it isn't read."""
    workspace, stored = pod_dirs
    workspace.mkdir()
    path = workspace / "a.txt"
    path.write_text("aaaa")
    assert await proxy.sync_once() == ["a.txt"]

    before = path.stat()
    path.write_text("bbbb")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))

    assert await proxy.sync_once() == []
    assert (stored / "a.txt").read_text() == "aaaa"


async def test_deleted_file_is_deleted_from_the_store(pod_dirs):
    """A hydrated file deleted from /workspace is deleted from the store too."""
    workspace, stored = pod_dirs
    (stored / "data").mkdir(parents=True)
    (stored / "qc.py").write_text("# qc\n")
    (stored / "data" / "old.csv").write_text("x\n")
    await proxy.hydrate_async()
    proxy._seed_from_disk()

    (workspace / "data" / "old.csv").unlink()
    await proxy.sync_once()

    assert not (stored / "data" / "old.csv").exists()
    assert (stored / "qc.py").read_text() == "# qc\n"


async def test_a_file_deleted_from_the_store_is_not_put_back(pod_dirs):
    """A file the dashboard deletes while the pod holds it stays deleted, edits and all."""
    workspace, stored = pod_dirs
    stored.mkdir(parents=True)
    (stored / "qc.py").write_text("# qc\n")
    await proxy.hydrate_async()
    proxy._seed_from_disk()
    (workspace / "made.py").write_text("# made here\n")
    assert await proxy.sync_once() == ["made.py"]

    (stored / "qc.py").unlink()
    (stored / "made.py").unlink()
    (workspace / "qc.py").write_text("# qc, as marimo rewrote it on open\n")
    (workspace / "made.py").write_text("# made here, edited\n")
    (workspace / "new.py").write_text("# new\n")

    assert await proxy.sync_once() == ["new.py"]
    assert not (stored / "qc.py").exists()
    assert not (stored / "made.py").exists()
    (workspace / "qc.py").write_text("# qc, edited again\n")
    assert await proxy.sync_once() == []
    assert not (stored / "qc.py").exists()


async def test_a_notebook_that_did_not_hydrate_is_never_saved(pod_dirs, monkeypatch):
    """The blank marimo opens for a notebook gone from the store never reaches it."""
    workspace, stored = pod_dirs
    monkeypatch.setenv("SG_UNSAVED_NOTEBOOK", "qc.py")
    await proxy.hydrate_async()
    proxy._seed_from_disk()
    (workspace / "qc.py").write_text("")
    (workspace / "other.py").write_text("# other\n")

    assert await proxy.sync_once() == ["other.py"]
    (workspace / "qc.py").write_text("# typed into the blank\n")
    assert await proxy.sync_once() == []
    assert not (stored / "qc.py").exists()


async def test_store_files_the_pod_never_had_are_kept(pod_dirs):
    """After a failed hydrate the workspace is empty, and saving mustn't wipe the store."""
    workspace, stored = pod_dirs
    stored.mkdir(parents=True)
    (stored / "qc.py").write_text("# qc\n")
    workspace.mkdir()

    await proxy.sync_once()

    assert (stored / "qc.py").read_text() == "# qc\n"


def test_file_over_the_limit_is_not_saved_and_is_reported(
    pod_dirs, owner_client, monkeypatch
):
    """A file over the limit isn't saved, and the save status names it for the banner."""
    monkeypatch.setattr(proxy, "MAX_SAVED_BYTES", 10)
    workspace, stored = pod_dirs
    workspace.mkdir()
    (workspace / "qc.py").write_text("# qc\n")
    assert owner_client.get("/__sg__/save-status").json() == {
        "limit_bytes": 10,
        "unsaved": [],
        "not_loaded": None,
    }

    big = workspace / "data" / "big.h5ad"
    big.parent.mkdir()
    big.write_bytes(b"x" * 11)

    assert asyncio.run(proxy.sync_once()) == ["qc.py"]
    assert not (stored / "data" / "big.h5ad").exists()
    assert owner_client.get("/__sg__/save-status").json() == {
        "limit_bytes": 10,
        "unsaved": [{"path": "data/big.h5ad", "bytes": 11}],
        "not_loaded": None,
    }


def test_save_status_names_the_notebook_that_did_not_load(
    pod_dirs, owner_client, monkeypatch
):
    """The banner learns the open notebook didn't load, so it can say edits are lost."""
    workspace, _ = pod_dirs
    workspace.mkdir()
    monkeypatch.setenv("SG_UNSAVED_NOTEBOOK", "qc.py")

    assert owner_client.get("/__sg__/save-status").json()["not_loaded"] == "qc.py"


def test_interval_from_env_saves_while_serving(pod_dirs, monkeypatch):
    """The pod saves on the interval its env sets, while it serves."""
    workspace, stored = pod_dirs
    monkeypatch.setenv("SG_SAVE_INTERVAL_SECONDS", "0.1")
    proxy.hydrate()

    with TestClient(proxy.asgi_app):
        (workspace / "live.py").write_text("# live\n")
        deadline = time.monotonic() + 2
        while not (stored / "live.py").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert (stored / "live.py").read_text() == "# live\n"


def test_interval_zero_saves_only_at_shutdown(pod_dirs, monkeypatch):
    """An interval of 0 turns the periodic save off; shutdown still saves."""
    workspace, stored = pod_dirs
    monkeypatch.setenv("SG_SAVE_INTERVAL_SECONDS", "0")
    proxy.hydrate()

    with TestClient(proxy.asgi_app):
        (workspace / "late.py").write_text("# late edit\n")
        time.sleep(0.5)
        assert not (stored / "late.py").exists()

    assert (stored / "late.py").read_text() == "# late edit\n"


# ---------------------------------------------------------------------------
# Agent sign-ins: stored beside the workspace, put back at launch
# ---------------------------------------------------------------------------


def test_hydrate_puts_back_stored_sign_ins_for_the_owner_only(pod_home):
    """A sign-in stored by an earlier pod is back in the home dir, readable by the owner alone."""
    home, stored = pod_home
    (stored / ".claude").mkdir(parents=True)
    (stored / ".claude" / ".credentials.json").write_text('{"token": "t"}')

    proxy.hydrate()

    restored = home / ".claude" / ".credentials.json"
    assert restored.read_text() == '{"token": "t"}'
    assert restored.stat().st_mode & 0o777 == 0o600
    assert not (proxy.WORKSPACE_DIR / ".claude").exists()


async def test_a_sign_in_is_saved_once_and_nothing_else_from_home(pod_home):
    """Each agent's sign-in file saves when it changes; the rest of home never does."""
    home, stored = pod_home
    await proxy.hydrate_async()
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / ".credentials.json").write_text('{"token": "t"}')
    (home / ".claude.json").write_text('{"oauthAccount": {}}')
    (home / ".claude" / "history.jsonl").write_text("prompt\n")
    (home / ".local" / "share" / "opencode").mkdir(parents=True)
    (home / ".local" / "share" / "opencode" / "auth.json").write_text('{"k": 1}')

    assert await proxy.save_sign_ins() == [
        ".claude/.credentials.json",
        ".claude.json",
        ".local/share/opencode/auth.json",
    ]
    assert await proxy.save_sign_ins() == []
    assert (stored / ".claude" / ".credentials.json").read_text() == '{"token": "t"}'
    assert (stored / ".local" / "share" / "opencode" / "auth.json").exists()
    assert not (stored / ".claude" / "history.jsonl").exists()


async def test_signing_out_deletes_the_stored_sign_in(pod_home):
    """A sign-in file gone from home is gone from the store, so a sign-out lasts."""
    home, stored = pod_home
    (stored / ".claude").mkdir(parents=True)
    (stored / ".claude" / ".credentials.json").write_text('{"token": "t"}')
    await proxy.hydrate_async()
    proxy._seed_from_disk()

    (home / ".claude" / ".credentials.json").unlink()

    assert await proxy.save_sign_ins() == [".claude/.credentials.json"]
    assert not (stored / ".claude" / ".credentials.json").exists()


def test_a_sign_in_is_saved_at_shutdown(pod_home, monkeypatch):
    """A sign-in made just before the pod stops survives it."""
    home, stored = pod_home
    monkeypatch.setenv("SG_SAVE_INTERVAL_SECONDS", "0")
    proxy.hydrate()

    with TestClient(proxy.asgi_app):
        (home / ".local" / "share" / "opencode").mkdir(parents=True)
        (home / ".local" / "share" / "opencode" / "auth.json").write_text('{"k": 1}')

    assert (stored / ".local" / "share" / "opencode" / "auth.json").exists()
