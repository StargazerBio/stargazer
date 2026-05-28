"""Tests for the admin app: AppEnvironment, session model, and routes.

Route tests use FastAPI's `TestClient` instantiated WITHOUT the context
manager so the app's lifespan (`init()` → Flyte client) never runs — the
routes under test return before any control-plane call. A `SESSION_SECRET`
is injected per test and signed session cookies are minted with the real
`app.session` helpers so the auth path exercises production code.
"""

import pytest
from fastapi.testclient import TestClient

from app.admin_app import _dashboard_context, _workspace_tiles, asgi_app
from app.notebooks import TEMPLATE_SLUG, TEMPLATE_TITLE
from app.session import (
    SESSION_COOKIE,
    SessionData,
    create_session_cookie,
    read_session_cookie,
)


SECRET = "test-session-secret"


@pytest.fixture
def secret_env(monkeypatch):
    """Set SESSION_SECRET so routes can read and sign the session cookie."""
    monkeypatch.setenv("SESSION_SECRET", SECRET)
    return SECRET


@pytest.fixture
def client():
    """A TestClient that does not trigger the app lifespan (no Flyte init)."""
    return TestClient(asgi_app)


def _auth(client: TestClient, *, fork_owner: str = "", access_token: str = "") -> None:
    """Attach a signed session cookie for `octocat` to the client's jar."""
    data = SessionData(
        "octocat", 123, fork_owner=fork_owner, access_token=access_token
    )
    client.cookies.set(SESSION_COOKIE, create_session_cookie(data, SECRET))


# ---------------------------------------------------------------------------
# AppEnvironment / entrypoint
# ---------------------------------------------------------------------------


def test_app_env_is_valid_app_environment():
    """app_env is a properly configured AppEnvironment."""
    from flyte.app import AppEnvironment

    from app.admin_app import app_env

    assert isinstance(app_env, AppEnvironment)
    assert app_env.name == "admin-app"
    assert app_env.get_port().port == 8080


def test_main_function_exists():
    """admin_app exposes a main() entry point."""
    from app.admin_app import main

    assert callable(main)


# ---------------------------------------------------------------------------
# SessionData.workspace_enabled
# ---------------------------------------------------------------------------


def test_workspace_enabled_false_by_default():
    """A fresh session (no fork) reports workspace saving as off."""
    assert SessionData("u", 1).workspace_enabled is False


def test_workspace_enabled_requires_both_fork_and_token():
    """Opt-in requires both a fork_owner and an access_token."""
    assert SessionData("u", 1, fork_owner="u").workspace_enabled is False
    assert SessionData("u", 1, access_token="t").workspace_enabled is False
    assert SessionData("u", 1, fork_owner="u", access_token="t").workspace_enabled


# ---------------------------------------------------------------------------
# Workspace tile assembly
# ---------------------------------------------------------------------------


def test_workspace_tiles_leads_with_template():
    """The template starter heads the Workspace list even with no synced files."""
    tiles = _workspace_tiles([])
    assert len(tiles) == 1
    assert tiles[0]["slug"] == TEMPLATE_SLUG
    assert tiles[0]["title"] == TEMPLATE_TITLE
    assert tiles[0]["section"] == "workspace"


def test_workspace_tiles_dedupes_template_and_preserves_order():
    """A synced template.py is not duplicated; discovered files follow."""
    slugs = [t["slug"] for t in _workspace_tiles(["template.py", "my_analysis.py"])]
    assert slugs == ["template", "my_analysis"]


def test_dashboard_context_off_has_no_workspace_tiles():
    """When opt-in is off, no Workspace tiles are built."""
    ctx = _dashboard_context("octocat", ["template.py"], False)
    assert ctx["workspace_enabled"] is False
    assert ctx["workspace"] == []


def test_dashboard_context_on_builds_workspace_tiles():
    """When opt-in is on, Workspace tiles are built (template + discovered)."""
    ctx = _dashboard_context("octocat", ["foo.py"], True)
    assert ctx["workspace_enabled"] is True
    assert [t["slug"] for t in ctx["workspace"]] == ["template", "foo"]


# ---------------------------------------------------------------------------
# /launch gating
# ---------------------------------------------------------------------------


def test_launch_requires_session(secret_env, client):
    """Unauthenticated /launch is rejected with 401."""
    resp = client.post(
        "/launch",
        data={"slug": "assets", "mode": "edit", "section": "tutorials"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 401


def test_launch_workspace_blocked_without_optin(secret_env, client):
    """Workspace launches are gated behind opt-in: 403 when saving is off."""
    _auth(client)  # logged in, but no fork → saving off
    resp = client.post(
        "/launch",
        data={"slug": "template", "mode": "edit", "section": "workspace"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 403
    assert "enable workspace saving" in resp.json()["error"].lower()


def test_launch_invalid_mode_rejected(secret_env, client):
    """An invalid launch mode is rejected with 400."""
    _auth(client)
    resp = client.post(
        "/launch",
        data={"slug": "assets", "mode": "bogus", "section": "tutorials"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /workspace/enable opt-in
# ---------------------------------------------------------------------------


def test_workspace_enable_requires_session(secret_env, client):
    """Enabling without a session redirects home and sets no cookie."""
    resp = client.post("/workspace/enable", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"
    assert resp.cookies.get(SESSION_COOKIE) is None


def test_workspace_enable_forks_and_sets_cookie(secret_env, client, monkeypatch):
    """A successful opt-in forks, then re-signs a cookie with fork_owner set."""

    async def fake_fork(_token):
        return {"owner": {"login": "octocat"}}

    monkeypatch.setattr("app.admin_app.fork_upstream", fake_fork)
    _auth(client, access_token="gho_token")  # logged in, not yet enabled

    resp = client.post("/workspace/enable", follow_redirects=False)
    assert resp.status_code == 303

    new_cookie = resp.cookies.get(SESSION_COOKIE)
    assert new_cookie is not None
    session = read_session_cookie(new_cookie, SECRET)
    assert session.fork_owner == "octocat"
    assert session.workspace_enabled is True


def test_workspace_enable_failure_leaves_saving_off(secret_env, client, monkeypatch):
    """If the fork fails, the session is untouched (saving stays off)."""

    async def boom(_token):
        raise RuntimeError("github down")

    monkeypatch.setattr("app.admin_app.fork_upstream", boom)
    _auth(client, access_token="gho_token")

    resp = client.post("/workspace/enable", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.cookies.get(SESSION_COOKIE) is None  # no re-signed cookie


# ---------------------------------------------------------------------------
# /stop
# ---------------------------------------------------------------------------


def test_stop_requires_session(secret_env, client):
    """Unauthenticated /stop is rejected with 401."""
    resp = client.post("/stop", data={"slug": "assets", "mode": "edit"})
    assert resp.status_code == 401
