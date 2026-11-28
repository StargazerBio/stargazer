"""Tests for the notebook proxy (`runtime/proxy.py`).

The proxy is baked into the notebook image as a standalone module; here we
import it directly. Covered: what the proxy forwards from the platform-forwarded
`X-User-Subject`, the signed-token gate on Union, what is (not) forwarded to
marimo, the starting page while marimo is cold, the agent bridge, agent-redirect
and refused-write banner injection and streaming passthrough, the notebook
manifest's conditional writes against an in-memory object store, and the agents'
sign-ins against a local store root through the real `flyte.storage` calls. The
upstream marimo server is faked with an `httpx.MockTransport` installed as the
proxy's shared upstream client. The volume mount itself needs Union's broker and
isn't covered here.
"""

import asyncio
import json
import os
import sys
import threading
import time
from typing import ClassVar

import httpx
import obstore
import obstore.store
import pytest
import uvicorn
import websockets.asyncio.server
from conftest import load_proxy
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

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


class _DroppedPanel:
    """A panel connection whose client hung up without a close frame."""

    query_params: ClassVar[dict[str, str]] = {}

    async def accept(self) -> None:
        """Accept, as starlette's WebSocket does."""

    async def receive(self) -> dict:
        """The disconnect message starlette hands over when the client is gone."""
        return {"type": "websocket.disconnect", "code": 1006}

    async def send_text(self, text: str) -> None:
        """Drop what the agent prints."""

    async def close(self, code: int = 1000) -> None:
        """Raise as starlette does on a socket the client already dropped."""
        raise WebSocketDisconnect(code=1006)


async def test_agent_bridge_returns_when_the_panel_hung_up(monkeypatch):
    """A client that drops the connection ends the bridge without an error."""
    monkeypatch.setitem(
        proxy.AGENT_COMMANDS, "claude", [sys.executable, "-c", _FAKE_AGENT]
    )

    await proxy.agent_bridge(_DroppedPanel(), "claude")


# ---------------------------------------------------------------------------
# Handing a channel over to a successor connection
# ---------------------------------------------------------------------------

# Answers each line with its process id, the line's number and the line, so a
# test can tell whether two connections reached the same process, and in what
# order its lines arrived.
_COUNTING_AGENT = """
import os, sys
for n, line in enumerate(sys.stdin, 1):
    print(os.getpid(), n, line.rstrip(), flush=True)
"""


@pytest.fixture
def counting_agent(monkeypatch):
    """`claude` is the counting agent."""
    monkeypatch.setitem(
        proxy.AGENT_COMMANDS, "claude", [sys.executable, "-c", _COUNTING_AGENT]
    )


@pytest.fixture
def live_proxy():
    """The proxy under a real uvicorn server on a free port; yields its ws:// base.

    A handover spans two connections on one event loop, which TestClient, with
    a loop per connection, can't give.
    """
    config = uvicorn.Config(
        proxy.asgi_app, host="127.0.0.1", port=0, lifespan="off", log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    yield f"ws://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
    server.should_exit = True
    thread.join(5)


def test_a_successor_connection_takes_over_the_agent(live_proxy, counting_agent):
    """The successor reaches the same agent process, and the old connection is closed with 4000."""
    url = f"{live_proxy}/__sg__/agent/claude?__sg_rid=r1"
    with connect(url) as old:
        old.send("a")
        pid, _, _ = old.recv(timeout=5).split()
        old.send("b")
        assert old.recv(timeout=5) == f"{pid} 2 b"
        with connect(f"{url}&__sg_resume=2") as new:
            with pytest.raises(ConnectionClosed) as closed:
                old.recv(timeout=5)
            new.send("c")
            assert new.recv(timeout=5) == f"{pid} 3 c"
    assert closed.value.rcvd.code == 4000


def test_a_successor_waits_for_what_the_old_connection_sent(live_proxy, counting_agent):
    """A frame the page sent on the old connection reaches the agent before any sent on the successor."""
    url = f"{live_proxy}/__sg__/agent/claude?__sg_rid=r2"
    with connect(url) as old:
        old.send("a")
        pid, _, _ = old.recv(timeout=5).split()
        with connect(f"{url}&__sg_resume=2") as new:
            new.send("c")
            old.send("b")
            with pytest.raises(ConnectionClosed):
                while True:
                    old.recv(timeout=5)
            heard = [new.recv(timeout=5)]
            if heard[0] != f"{pid} 3 c":
                heard.append(new.recv(timeout=5))
    assert heard[-1] == f"{pid} 3 c"


def test_taking_over_a_channel_that_is_gone_is_refused(live_proxy, counting_agent):
    """A channel whose connection closed with no successor ends with it."""
    url = f"{live_proxy}/__sg__/agent/claude?__sg_rid=r3"
    with connect(url) as ws:
        ws.send("a")
        ws.recv(timeout=5)
    with (
        connect(f"{url}&__sg_resume=0") as late,
        pytest.raises(ConnectionClosed) as refused,
    ):
        late.recv(timeout=5)
    assert refused.value.rcvd.code == 4404


@pytest.fixture
def marimo_socket(monkeypatch):
    """A websocket echo server standing in for marimo; returns the paths it was opened at."""
    paths: list[str] = []
    ready = threading.Event()
    loop = asyncio.new_event_loop()
    stop = loop.create_future()

    async def echo(conn):
        """Record the path, then echo every frame."""
        paths.append(conn.request.path)
        async for msg in conn:
            await conn.send(msg)

    async def serve():
        """Serve on a free port until told to stop."""
        async with websockets.asyncio.server.serve(echo, "127.0.0.1", 0) as server:
            monkeypatch.setattr(
                proxy, "MARIMO_HTTP_PORT", server.sockets[0].getsockname()[1]
            )
            ready.set()
            await stop

    thread = threading.Thread(target=lambda: loop.run_until_complete(serve()))
    thread.start()
    ready.wait(5)
    yield paths
    loop.call_soon_threadsafe(stop.set_result, None)
    thread.join(5)


def test_a_successor_takes_over_the_marimo_socket(live_proxy, marimo_socket):
    """marimo sees one connection, opened without the page's channel parameters."""
    url = f"{live_proxy}/ws?session_id=s_1&__sg_rid=r4"
    with connect(url) as old:
        old.send("x")
        assert old.recv(timeout=5) == "x"
        with connect(f"{url}&__sg_resume=1") as new:
            with pytest.raises(ConnectionClosed):
                old.recv(timeout=5)
            new.send(b"y")
            assert new.recv(timeout=5) == b"y"
    assert marimo_socket == ["/ws?session_id=s_1"]


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


def test_proxy_injects_the_agent_redirect_into_html(owner_client, upstream):
    """HTML gets the agent redirect before </body>, and no banner."""
    _serve_html(upstream)

    resp = owner_client.get("/")

    assert resp.status_code == 200
    assert resp.content.index(b"/__sg__/agent/") < resp.content.index(b"</body>")
    assert b"/__sg__/term" not in resp.content
    assert b"no longer save" not in resp.content


def test_proxy_warns_on_every_page_once_the_manifest_refused_a_write(
    owner_client, upstream, monkeypatch, tmp_path
):
    """After a refused manifest write the page says its changes no longer save."""
    notebook = proxy._NotebookVolume(
        obstore.store.MemoryStore(), "m.json", tmp_path, True
    )
    monkeypatch.setattr(proxy, "_notebook", notebook)
    _serve_html(upstream)
    assert b"no longer save" not in owner_client.get("/").content

    notebook.refused = True

    page = owner_client.get("/").content
    assert page.index(b"no longer save") < page.index(b"</body>")


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
# The notebook's volume: change detection and the manifest's conditional writes
# ---------------------------------------------------------------------------


def _manifest_store(tmp_path):
    """An in-memory store holding a notebook's manifest, and a volume wrapper on it.

    The wrapper has no volume: only the manifest side is exercised.
    """
    store = obstore.store.MemoryStore()
    first = obstore.put(
        store,
        "m.json",
        json.dumps({"locator": "s3://b/v1", "file": "nb.py", "source": "v1"}).encode(),
        mode="create",
    )
    notebook = proxy._NotebookVolume(store, "m.json", tmp_path, True)
    notebook.file = "nb.py"
    notebook.etag = first["e_tag"]
    return store, notebook


def _manifest(store):
    """The manifest object's current content."""
    return json.loads(bytes(obstore.get(store, "m.json").bytes()))


async def test_manifest_names_each_version_with_the_notebook_text(tmp_path):
    """Each commit's locator and the file's text replace the manifest's, in turn."""
    store, notebook = _manifest_store(tmp_path)

    await notebook._write_manifest("s3://b/v2", "second")
    await notebook._write_manifest("s3://b/v3", "third")

    assert _manifest(store) == {
        "locator": "s3://b/v3",
        "file": "nb.py",
        "source": "third",
    }
    assert not notebook.refused


async def test_a_manifest_written_elsewhere_stops_this_pod_writing_it(tmp_path, capsys):
    """A refused write leaves the other writer's manifest alone, for good."""
    store, notebook = _manifest_store(tmp_path)
    other = {"locator": "s3://b/dashboard", "file": "nb.py", "source": "theirs"}
    obstore.put(store, "m.json", json.dumps(other).encode(), mode="overwrite")

    await notebook._write_manifest("s3://b/v2", "mine")
    await notebook._write_manifest("s3://b/v3", "mine too")

    assert _manifest(store) == other
    assert notebook.refused
    out = capsys.readouterr().out
    assert "s3://b/v2" in out
    assert "s3://b/v3" in out


async def test_a_manifest_deleted_elsewhere_stops_this_pod_writing_it(tmp_path, capsys):
    """A notebook deleted from the dashboard stays deleted: the pod's write is refused."""
    store, notebook = _manifest_store(tmp_path)
    obstore.delete(store, "m.json")

    await notebook._write_manifest("s3://b/v2", "mine")
    await notebook._write_manifest("s3://b/v3", "mine too")

    assert notebook.refused
    assert obstore.list(store).collect() == []
    out = capsys.readouterr().out
    assert "s3://b/v2" in out
    assert "s3://b/v3" in out


def test_volume_changes_are_files_that_changed_outside_the_caches(tmp_path):
    """A new or rewritten file changes the stamp; caches and sessions don't."""
    folder = tmp_path / "notebook"
    folder.mkdir()
    (folder / "nb.py").write_text("v1")
    before = proxy._volume_stamp(folder)

    (folder / "__pycache__").mkdir()
    (folder / "__pycache__" / "nb.pyc").write_text("x")
    (folder / "__marimo__").mkdir()
    (folder / "__marimo__" / "session.json").write_text("x")
    assert proxy._volume_stamp(folder) == before
    assert list(before) == ["nb.py"]

    (folder / "nb.py").write_text("v2, longer")
    assert proxy._volume_stamp(folder) != before
    (folder / "data").mkdir()
    (folder / "data" / "counts.csv").write_text("a,b\n")
    assert sorted(proxy._volume_stamp(folder)) == ["data/counts.csv", "nb.py"]


async def test_no_manifest_mounts_nothing(monkeypatch):
    """A built-in notebook, or a local run, has no volume and keeps its directory."""
    monkeypatch.delenv("SG_NOTEBOOK_MANIFEST", raising=False)
    cwd = os.getcwd()

    assert await proxy._open_notebook() is None
    assert os.getcwd() == cwd


# ---------------------------------------------------------------------------
# Agent sign-ins: stored beside the workspace, put back at launch
# ---------------------------------------------------------------------------


@pytest.fixture
def pod_home(tmp_path, monkeypatch):
    """The pod's home directory and where the owner's sign-ins are stored."""
    monkeypatch.setenv("STARGAZER_WORKSPACE_ROOT", str(tmp_path / "store"))
    monkeypatch.setattr(proxy, "_sign_ins_synced", {})
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path / "home", tmp_path / "store" / "users" / OWNER / "agents"


def test_restore_puts_back_stored_sign_ins_for_the_owner_only(pod_home):
    """A sign-in stored by an earlier pod is back in the home dir, readable by the owner alone."""
    home, stored = pod_home
    (stored / ".claude").mkdir(parents=True)
    (stored / ".claude" / ".credentials.json").write_text('{"token": "t"}')

    proxy.restore_sign_ins()

    restored = home / ".claude" / ".credentials.json"
    assert restored.read_text() == '{"token": "t"}'
    assert restored.stat().st_mode & 0o777 == 0o600


async def test_a_sign_in_is_saved_once_and_nothing_else_from_home(pod_home):
    """Each agent's sign-in file saves when it changes; the rest of home never does."""
    home, stored = pod_home
    await proxy.restore_sign_ins_async()
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
    await proxy.restore_sign_ins_async()
    proxy._seed_from_disk()

    (home / ".claude" / ".credentials.json").unlink()

    assert await proxy.save_sign_ins() == [".claude/.credentials.json"]
    assert not (stored / ".claude" / ".credentials.json").exists()


def test_a_sign_in_is_saved_at_shutdown(pod_home, monkeypatch):
    """A sign-in made just before the pod stops survives it."""
    home, stored = pod_home
    monkeypatch.setenv("SG_SAVE_INTERVAL_SECONDS", "0")
    proxy.restore_sign_ins()

    with TestClient(proxy.asgi_app):
        (home / ".local" / "share" / "opencode").mkdir(parents=True)
        (home / ".local" / "share" / "opencode" / "auth.json").write_text('{"k": 1}')

    assert (stored / ".local" / "share" / "opencode" / "auth.json").exists()
