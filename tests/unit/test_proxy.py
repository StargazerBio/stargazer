"""Tests for the per-notebook proxy (`app.proxy`).

The proxy is baked into the notebook image as a standalone module; here we
import it directly. Covered: the owner gate on the platform-forwarded
`X-User-Subject`, what is (not) forwarded to marimo, the starting page while
marimo is cold, terminal-overlay injection and streaming passthrough, and the
workspace hydrate/sync against a local store root through the real
`flyte.storage` calls. The upstream marimo server is faked with an
`httpx.MockTransport` installed as the proxy's shared upstream client.
"""

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import proxy

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
# Owner gate
# ---------------------------------------------------------------------------


def test_owner_request_reaches_marimo(owner_client, upstream):
    """The pod's owner is forwarded through to marimo."""
    recorder = upstream(lambda req: httpx.Response(200, text="hello"))

    resp = owner_client.get("/api/status")

    assert resp.status_code == 200
    assert resp.text == "hello"
    assert recorder["url"] == "http://127.0.0.1:8081/api/status"


def test_other_user_gets_403(upstream):
    """Another signed-in member can't use someone else's notebook."""
    recorder = upstream(lambda req: httpx.Response(200, text="never"))
    client = TestClient(proxy.asgi_app, headers={"X-User-Subject": OTHER})

    resp = client.get("/")

    assert resp.status_code == 403
    assert "url" not in recorder


def test_missing_identity_gets_403(upstream):
    """No forwarded identity at all is denied."""
    recorder = upstream(lambda req: httpx.Response(200, text="never"))

    resp = TestClient(proxy.asgi_app).get("/")

    assert resp.status_code == 403
    assert "url" not in recorder


def test_unconfigured_owner_fails_closed(monkeypatch, owner_client, upstream):
    """A pod that doesn't know its owner denies everyone."""
    monkeypatch.delenv("SG_OWNER_SUBJECT")
    recorder = upstream(lambda req: httpx.Response(200, text="never"))

    resp = owner_client.get("/")

    assert resp.status_code == 403
    assert "url" not in recorder


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


@pytest.mark.parametrize("path", ["/__sg__/term", "/ws"])
def test_websockets_deny_other_users(path):
    """The terminal and marimo websockets apply the same owner gate."""
    client = TestClient(proxy.asgi_app, headers={"X-User-Subject": OTHER})
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect(path) as ws,
    ):
        ws.receive_text()
    assert exc.value.code == 1008


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
# Dropdown terminal — secret scrub + HTML overlay injection
# ---------------------------------------------------------------------------


def test_shell_env_scrubs_named_secrets(monkeypatch):
    """Named secrets stay out of the interactive shell's environment."""
    monkeypatch.setenv("PINATA_JWT", "pinata-secret")
    monkeypatch.setenv("PINATA_GATEWAY", "https://dweb.link")  # not a secret

    env = proxy._shell_env()

    assert "PINATA_JWT" not in env
    assert env["PINATA_GATEWAY"] == "https://dweb.link"


def test_shell_env_scrubs_secret_shaped_suffixes(monkeypatch):
    """Future secret-shaped vars are dropped by suffix without an explicit entry."""
    monkeypatch.setenv("SOME_API_TOKEN", "x")
    monkeypatch.setenv("DB_PASSWORD", "x")
    monkeypatch.setenv("SIGNING_KEY", "x")
    monkeypatch.setenv("WEBHOOK_SECRET", "x")
    monkeypatch.setenv("THIRDPARTY_JWT", "x")
    monkeypatch.setenv("HARMLESS_VALUE", "keep")

    env = proxy._shell_env()

    for leaked in (
        "SOME_API_TOKEN",
        "DB_PASSWORD",
        "SIGNING_KEY",
        "WEBHOOK_SECRET",
        "THIRDPARTY_JWT",
    ):
        assert leaked not in env
    assert env["HARMLESS_VALUE"] == "keep"
    assert env["TERM"] == "xterm-256color"


def test_term_injection_targets_body_close():
    """The overlay splices before </body> and wires the /__sg__/term websocket."""
    html = b"<html><body><div id='app'></div></body></html>"
    injected = html.replace(b"</body>", proxy._TERM_INJECTION + b"</body>", 1)

    assert b"/__sg__/term" in injected
    assert b"sg-term-overlay" in injected
    assert injected.index(b"sg-term-overlay") < injected.index(b"</body>")


# ---------------------------------------------------------------------------
# Forwarding path — HTML injection, streaming, query passthrough
# ---------------------------------------------------------------------------


def test_proxy_injects_terminal_into_html(owner_client, upstream):
    """HTML responses get the terminal overlay spliced in before </body>."""
    upstream(
        lambda req: httpx.Response(
            200,
            content=b"<html><body><div id='app'></div></body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    resp = owner_client.get("/")

    assert resp.status_code == 200
    assert b"sg-term-overlay" in resp.content
    assert resp.content.index(b"sg-term-overlay") < resp.content.index(b"</body>")


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
    """Point the pod's workspace/snapshot dirs and the store root at tmp paths."""
    store = tmp_path / "store"
    monkeypatch.setenv("STARGAZER_WORKSPACE_ROOT", str(store))
    monkeypatch.setattr(proxy, "WORKSPACE_DIR", tmp_path / "workspace")
    monkeypatch.setattr(proxy, "SNAPSHOT_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(proxy, "_synced", {})
    notebooks = store / "users" / OWNER / "notebooks"
    snapshots = store / "users" / OWNER / "snapshots"
    return tmp_path / "workspace", tmp_path / "snapshots", notebooks, snapshots


def test_hydrate_pulls_owner_notebooks_and_snapshots(pod_dirs):
    """Launch fills /workspace and /snapshots from the owner's stored notebooks."""
    workspace, snaps, notebooks, snapshots = pod_dirs
    notebooks.mkdir(parents=True)
    snapshots.mkdir(parents=True)
    (notebooks / "qc.py").write_text("# qc\n")
    (snapshots / "frozen.py").write_text("# frozen\n")

    proxy.hydrate()

    assert (workspace / "qc.py").read_text() == "# qc\n"
    assert (snaps / "frozen.py").read_text() == "# frozen\n"


def test_hydrate_new_user_gets_empty_dirs(pod_dirs):
    """A user with nothing stored starts with empty, existing directories."""
    workspace, snaps, _, _ = pod_dirs

    proxy.hydrate()

    assert sorted(p.name for p in workspace.iterdir()) == []
    assert sorted(p.name for p in snaps.iterdir()) == []


async def test_sync_uploads_only_changed_notebooks(pod_dirs):
    """Unchanged hydrated files stay put; edits and new notebooks upload."""
    workspace, _, notebooks, _ = pod_dirs
    notebooks.mkdir(parents=True)
    (notebooks / "qc.py").write_text("# qc\n")
    await proxy.hydrate_async()

    assert await proxy.sync_once() == []

    (workspace / "qc.py").write_text("# qc v2\n")
    (workspace / "new.py").write_text("# new\n")
    (workspace / "_scratch.py").write_text("# private\n")

    assert await proxy.sync_once() == ["new.py", "qc.py"]
    assert (notebooks / "qc.py").read_text() == "# qc v2\n"
    assert (notebooks / "new.py").read_text() == "# new\n"
    assert not (notebooks / "_scratch.py").exists()
    assert await proxy.sync_once() == []


async def test_sync_never_writes_snapshots(pod_dirs):
    """Edits under /snapshots are never written back to the store."""
    _, snaps, _, snapshots = pod_dirs
    snapshots.mkdir(parents=True)
    (snapshots / "frozen.py").write_text("# frozen\n")
    await proxy.hydrate_async()

    (snaps / "frozen.py").write_text("# tampered\n")

    assert await proxy.sync_once() == []
    assert (snapshots / "frozen.py").read_text() == "# frozen\n"


def test_shutdown_flushes_pending_edits(pod_dirs, monkeypatch):
    """Scale-to-zero writes edits made since the last periodic sync."""
    workspace, _, notebooks, _ = pod_dirs
    monkeypatch.setattr(proxy, "SYNC_INTERVAL_SECONDS", 3600)
    proxy.hydrate()

    with TestClient(proxy.asgi_app):
        (workspace / "late.py").write_text("# late edit\n")

    assert (notebooks / "late.py").read_text() == "# late edit\n"
