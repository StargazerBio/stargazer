"""Tests for the admin app: AppEnvironment, session model, and routes.

Route tests use FastAPI's `TestClient` instantiated WITHOUT the context
manager so the app's lifespan (`init()` → Flyte client) never runs — the
routes under test return before any control-plane call. A `SESSION_SECRET`
is injected per test and signed session cookies are minted with the real
`app.session` helpers so the auth path exercises production code.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.admin_app import _dashboard_context, _workspace_tiles, asgi_app
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


def _auth(
    client: TestClient, *, fork_full_name: str = "", access_token: str = ""
) -> None:
    """Attach a signed session cookie for `octocat` to the client's jar."""
    data = SessionData(
        "octocat", 123, fork_full_name=fork_full_name, access_token=access_token
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
    """Opt-in requires both a fork_full_name and an access_token."""
    assert SessionData("u", 1, fork_full_name="u/stargazer").workspace_enabled is False
    assert SessionData("u", 1, access_token="t").workspace_enabled is False
    assert SessionData(
        "u", 1, fork_full_name="u/stargazer", access_token="t"
    ).workspace_enabled


def test_fork_owner_derived_from_full_name():
    """fork_owner is derived from fork_full_name's owner segment."""
    assert SessionData("u", 1, fork_full_name="alice/stargazer-1").fork_owner == "alice"
    assert SessionData("u", 1).fork_owner == ""


# ---------------------------------------------------------------------------
# Workspace tile assembly
# ---------------------------------------------------------------------------


def test_workspace_tiles_excludes_template():
    """The shipped template is never rendered as a tile."""
    assert _workspace_tiles(["template.py"]) == []


def test_workspace_tiles_lists_only_user_notebooks():
    """User-created notebooks become tiles; the template is filtered out."""
    slugs = [t["slug"] for t in _workspace_tiles(["template.py", "my_analysis.py"])]
    assert slugs == ["my_analysis"]


def test_dashboard_context_off_has_no_workspace_tiles():
    """When opt-in is off, no Workspace tiles are built."""
    ctx = _dashboard_context("octocat", ["foo.py"], False)
    assert ctx["workspace_enabled"] is False
    assert ctx["workspace"] == []


def test_dashboard_context_on_builds_workspace_tiles():
    """When opt-in is on, only the user's own notebooks become tiles."""
    ctx = _dashboard_context("octocat", ["template.py", "foo.py"], True)
    assert ctx["workspace_enabled"] is True
    assert [t["slug"] for t in ctx["workspace"]] == ["foo"]


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
    """A genuine fork is verified and recorded as fork_full_name."""

    async def fake_fork(_token):
        return {
            "fork": True,
            "full_name": "octocat/stargazer",
            "owner": {"login": "octocat"},
        }

    monkeypatch.setattr("app.admin_app.fork_upstream", fake_fork)
    _auth(client, access_token="gho_token")  # logged in, not yet enabled

    resp = client.post("/workspace/enable", follow_redirects=False)
    assert resp.status_code == 303

    new_cookie = resp.cookies.get(SESSION_COOKIE)
    assert new_cookie is not None
    session = read_session_cookie(new_cookie, SECRET)
    assert session.fork_full_name == "octocat/stargazer"
    assert session.workspace_enabled is True


def test_workspace_enable_refuses_collision_fork(secret_env, client, monkeypatch):
    """A collision fork (`stargazer-1`) is refused — only the canonical name.

    Detection at login only looks at the canonical `{user}/stargazer`, so
    recording an alias would silently break saving on the next login. We refuse
    instead and keep the two paths in lockstep.
    """

    async def fake_fork(_token):
        return {
            "fork": True,
            "full_name": "octocat/stargazer-1",
            "owner": {"login": "octocat"},
        }

    monkeypatch.setattr("app.admin_app.fork_upstream", fake_fork)
    _auth(client, access_token="gho_token")

    resp = client.post("/workspace/enable", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/?ws_error=fork"
    assert resp.cookies.get(SESSION_COOKIE) is None  # saving stays off


def test_workspace_enable_refuses_non_fork(secret_env, client, monkeypatch):
    """If forking returns the upstream source (transfer redirect), refuse."""

    async def fake_fork(_token):
        # Mimics POST /forks resolving to the source repo, not a fork.
        return {
            "fork": False,
            "full_name": "StargazerBio/stargazer",
            "owner": {"login": "StargazerBio"},
        }

    monkeypatch.setattr("app.admin_app.fork_upstream", fake_fork)
    _auth(client, access_token="gho_token")

    resp = client.post("/workspace/enable", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/?ws_error=fork"
    assert resp.cookies.get(SESSION_COOKIE) is None  # saving stays off


def test_workspace_enable_failure_leaves_saving_off(secret_env, client, monkeypatch):
    """If the fork call errors, the session is untouched (saving stays off)."""

    async def boom(_token):
        raise RuntimeError("github down")

    monkeypatch.setattr("app.admin_app.fork_upstream", boom)
    _auth(client, access_token="gho_token")

    resp = client.post("/workspace/enable", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.cookies.get(SESSION_COOKIE) is None  # no re-signed cookie


# ---------------------------------------------------------------------------
# /auth/callback — restore Workspace saving for returning users
# ---------------------------------------------------------------------------


def _patch_oauth(monkeypatch):
    """Stub the OAuth handshake so /auth/callback reaches the fork lookup."""

    async def fake_exchange(**_kw):
        return "gho_token"

    async def fake_user(_token):
        return {"login": "octocat", "id": 123}

    async def fake_provision(github_username):
        return None

    monkeypatch.setattr("app.admin_app.exchange_code", fake_exchange)
    monkeypatch.setattr("app.admin_app.get_github_user", fake_user)
    monkeypatch.setattr("app.admin_app.provision_user", fake_provision)


def _callback(client):
    """Drive /auth/callback with a matching oauth_state cookie."""
    client.cookies.set("oauth_state", "xyz")
    return client.get("/auth/callback?code=abc&state=xyz", follow_redirects=False)


def test_callback_restores_saving_for_returning_fork(secret_env, client, monkeypatch):
    """A returning user whose fork still exists gets Workspace saving back."""
    _patch_oauth(monkeypatch)

    async def fake_find(_token, _username):
        return {"full_name": "octocat/stargazer"}

    monkeypatch.setattr("app.admin_app.find_existing_fork", fake_find)

    resp = _callback(client)
    session = read_session_cookie(resp.cookies.get(SESSION_COOKIE), SECRET)
    assert session.fork_full_name == "octocat/stargazer"
    assert session.workspace_enabled is True


def test_callback_saving_off_when_no_fork(secret_env, client, monkeypatch):
    """A first-time user (no fork yet) starts with saving off."""
    _patch_oauth(monkeypatch)

    async def fake_find(_token, _username):
        return None

    monkeypatch.setattr("app.admin_app.find_existing_fork", fake_find)

    resp = _callback(client)
    session = read_session_cookie(resp.cookies.get(SESSION_COOKIE), SECRET)
    assert session.fork_full_name == ""
    assert session.workspace_enabled is False


def test_callback_fork_lookup_failure_does_not_block_login(
    secret_env, client, monkeypatch
):
    """A failing fork lookup must not break login — saving just stays off."""
    _patch_oauth(monkeypatch)

    async def boom(_token, _username):
        raise RuntimeError("github down")

    monkeypatch.setattr("app.admin_app.find_existing_fork", boom)

    resp = _callback(client)
    assert resp.status_code == 302
    session = read_session_cookie(resp.cookies.get(SESSION_COOKIE), SECRET)
    assert session.workspace_enabled is False


# ---------------------------------------------------------------------------
# /stop
# ---------------------------------------------------------------------------


def test_stop_requires_session(secret_env, client):
    """Unauthenticated /stop is rejected with 401."""
    resp = client.post("/stop", data={"slug": "assets", "mode": "edit"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /launch/status
# ---------------------------------------------------------------------------


class _FakeApp:
    """Stand-in for a flyte.remote.App in status tests."""

    def __init__(self, active: bool, endpoint: str):
        self._active, self._endpoint = active, endpoint

    def is_active(self) -> bool:
        """Whether the app is deployed and active."""
        return self._active

    @property
    def endpoint(self) -> str:
        """The app's public endpoint URL."""
        return self._endpoint


def _stub_app_get(monkeypatch, table: dict, deleted: list | None = None):
    """Patch admin_app.App so App.get.aio resolves names from `table`.

    App.delete.aio records deleted names into `deleted` when provided, so
    teardown paths (e.g. /workspace/delete) can be asserted.
    """

    class _Get:
        async def aio(self, name, project, domain):
            if name in table:
                return table[name]
            raise RuntimeError("not found")

    class _Delete:
        async def aio(self, name, project, domain):
            if deleted is not None:
                deleted.append(name)

    monkeypatch.setattr(
        "app.admin_app.App", SimpleNamespace(get=_Get(), delete=_Delete())
    )


def test_launch_status_requires_session(secret_env, client):
    """Unauthenticated /launch/status is rejected with 401."""
    resp = client.get("/launch/status")
    assert resp.status_code == 401


def test_launch_status_reports_only_active_apps(secret_env, client, monkeypatch):
    """Status returns active per-notebook apps with their endpoints."""
    _stub_app_get(monkeypatch, {"nb-assets-edit": _FakeApp(True, "http://nb.example")})

    _auth(client)  # no fork → workspace off → registry notebooks only
    resp = client.get("/launch/status", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    running = resp.json()["running"]
    assert running == [
        {"slug": "assets", "mode": "edit", "url": "http://nb.example"}
    ]


def test_launch_status_skips_inactive_apps(secret_env, client, monkeypatch):
    """A deployed-but-inactive app is not reported as running."""
    _stub_app_get(monkeypatch, {"nb-assets-edit": _FakeApp(False, "http://nb.example")})

    _auth(client)
    resp = client.get("/launch/status", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    assert resp.json()["running"] == []


# ---------------------------------------------------------------------------
# /workspace/save and /workspace/cleanup
# ---------------------------------------------------------------------------


def test_save_requires_session(secret_env, client):
    """Unauthenticated /workspace/save is rejected with 401."""
    resp = client.post("/workspace/save", data={"slug": "foo", "mode": "edit"})
    assert resp.status_code == 401


def test_save_requires_optin(secret_env, client):
    """Saving without workspace saving enabled is rejected with 403."""
    _auth(client)
    resp = client.post("/workspace/save", data={"slug": "foo", "mode": "edit"})
    assert resp.status_code == 403


def test_save_409_when_not_running(secret_env, client, monkeypatch):
    """Saving a notebook with no active pod is rejected with 409."""
    _stub_app_get(monkeypatch, {})  # App.get raises -> not running
    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post(
        "/workspace/save",
        data={"slug": "foo", "mode": "edit"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 409


def test_save_posts_to_app_endpoint(secret_env, client, monkeypatch):
    """Save POSTs the sync request to the notebook app's public endpoint."""
    from app import admin_app

    public = "http://nb-foo-edit-octocat-development.devbox.stargazer.bio"
    _stub_app_get(monkeypatch, {"nb-foo-edit": _FakeApp(True, public)})

    posted: dict = {}

    class _FakeAsyncClient:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def post(self, url, cookies=None):
            posted["url"] = url
            return SimpleNamespace(status_code=200, json=lambda: {"status": "ok"})

    monkeypatch.setattr(admin_app.httpx, "AsyncClient", _FakeAsyncClient)

    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post(
        "/workspace/save",
        data={"slug": "foo", "mode": "edit"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert posted["url"] == f"{public}/__sg__/workspace/sync"


def test_cleanup_requires_session(secret_env, client):
    """Unauthenticated /workspace/cleanup is rejected with 401."""
    resp = client.post("/workspace/cleanup")
    assert resp.status_code == 401


def test_cleanup_deletes_deactivated_apps_regardless_of_dashboard(
    secret_env, client, monkeypatch
):
    """Cleanup lists every nb-* app in the project and deletes the deactivated
    ones — including a deleted notebook's leftover that's on no dashboard list,
    while skipping active apps and non-notebook deployments."""

    class _App:
        def __init__(self, name, deactivated):
            self._name = name
            self._deactivated = deactivated

        @property
        def name(self):
            return self._name

        def is_deactivated(self):
            return self._deactivated

    # A deleted notebook's stopped app (in no registry/workspace listing), an
    # active app, and a non-notebook deployment.
    table = {
        "nb-deleted-edit": _App("nb-deleted-edit", True),
        "nb-running-run": _App("nb-running-run", False),
        "other-service": _App("other-service", True),
    }

    async def fake_list(project, domain="development", limit=500):
        return list(table.values())

    monkeypatch.setattr("app.admin_app.list_project_apps", fake_list)

    deleted: list = []

    class _Get:
        async def aio(self, name, project, domain):
            return table[name]

    class _Delete:
        async def aio(self, name, project, domain):
            deleted.append(name)

    monkeypatch.setattr(
        "app.admin_app.App", SimpleNamespace(get=_Get(), delete=_Delete())
    )

    _auth(client)
    resp = client.post("/workspace/cleanup", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    assert resp.json() == {"deleted": ["nb-deleted-edit"], "count": 1}
    assert deleted == ["nb-deleted-edit"]


def test_cleanup_listing_failure_returns_502(secret_env, client, monkeypatch):
    """If listing the project's apps fails, cleanup reports an error, not a 500."""

    async def boom(project, domain="development", limit=500):
        raise RuntimeError("control plane down")

    monkeypatch.setattr("app.admin_app.list_project_apps", boom)

    _auth(client)
    resp = client.post("/workspace/cleanup", headers={"Accept": "application/json"})
    assert resp.status_code == 502
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# /launch — workspace resource propagation
# ---------------------------------------------------------------------------


def _stub_serve(monkeypatch, sink: dict):
    """Replace flyte.with_servecontext so /launch never hits a control plane.

    The fake captures the served AppEnvironment in `sink['env']` and returns
    a deployment with a fixed endpoint.
    """

    async def fake_aio(env):
        sink["env"] = env
        return SimpleNamespace(endpoint="http://nb.example")

    ctx = SimpleNamespace(serve=SimpleNamespace(aio=fake_aio))
    monkeypatch.setattr("flyte.with_servecontext", lambda **_: ctx)


def test_launch_workspace_applies_notebook_resources(secret_env, client, monkeypatch):
    """A workspace launch parses [tool.stargazer] and serves those resources."""
    source = (
        "# /// script\n"
        '# dependencies = ["marimo"]\n'
        "#\n"
        "# [tool.stargazer]\n"
        "# cpu = 2\n"
        '# memory = "3Gi"\n'
        "# ///\n"
        "import marimo\n"
    )

    async def fake_fetch(_owner, _token, _filename):
        return source

    monkeypatch.setattr("app.admin_app.get_workspace_notebook", fake_fetch)
    sink: dict = {}
    _stub_serve(monkeypatch, sink)

    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post(
        "/launch",
        data={"slug": "analysis", "mode": "edit", "section": "workspace"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("http://nb.example")

    served = sink["env"]
    assert served.resources.cpu == 2
    assert served.resources.memory == "3Gi"


def test_launch_workspace_missing_source_uses_defaults(secret_env, client, monkeypatch):
    """If the notebook source can't be fetched, default resources are used."""

    async def fake_fetch(_owner, _token, _filename):
        return None

    monkeypatch.setattr("app.admin_app.get_workspace_notebook", fake_fetch)
    sink: dict = {}
    _stub_serve(monkeypatch, sink)

    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post(
        "/launch",
        data={"slug": "analysis", "mode": "edit", "section": "workspace"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200

    from app.notebook_meta import DEFAULT_RESOURCES

    served = sink["env"]
    assert served.resources.cpu == DEFAULT_RESOURCES.cpu
    assert served.resources.memory == DEFAULT_RESOURCES.memory


# ---------------------------------------------------------------------------
# /workspace/create
# ---------------------------------------------------------------------------


def _create_form(**overrides):
    """Default form fields for a create request."""
    form = {"name": "My Analysis", "source": "blank", "cpu": "2", "memory": "3Gi"}
    form.update(overrides)
    return form


def test_create_requires_session(secret_env, client):
    """Unauthenticated create is rejected with 401."""
    resp = client.post("/workspace/create", data=_create_form())
    assert resp.status_code == 401


def test_create_requires_optin(secret_env, client):
    """Create without workspace saving enabled is rejected with 403."""
    _auth(client)  # logged in, not opted in
    resp = client.post("/workspace/create", data=_create_form())
    assert resp.status_code == 403


def test_create_rejects_reserved_name(secret_env, client):
    """The reserved 'template' name is rejected with 400."""
    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post("/workspace/create", data=_create_form(name="Template"))
    assert resp.status_code == 400


def test_create_conflict_when_notebook_exists(secret_env, client, monkeypatch):
    """A name that already exists on the fork is rejected with 409."""

    async def fake_fetch(_owner, _token, _filename):
        return "# existing notebook\n"

    monkeypatch.setattr("app.admin_app.get_workspace_notebook", fake_fetch)
    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post("/workspace/create", data=_create_form(name="taken"))
    assert resp.status_code == 409


def test_create_blank_writes_file_and_returns_slug(secret_env, client, monkeypatch):
    """A blank create copies the blank seed, injects resources, returns slug."""
    blank_seed = (
        "# /// script\n"
        '# dependencies = ["marimo", "stargazer"]\n'
        "# ///\n"
        "import marimo\n"
    )
    written: dict = {}

    async def fake_fetch(_owner, _token, filename):
        # No collision for the new name; return the blank seed for blank.py.
        return blank_seed if filename == "blank.py" else None

    async def fake_create(owner, token, filename, content, message=None):
        written.update(filename=filename, content=content)
        return {"content": {"name": filename}}

    monkeypatch.setattr("app.admin_app.get_workspace_notebook", fake_fetch)
    monkeypatch.setattr("app.admin_app.create_workspace_notebook", fake_create)

    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post(
        "/workspace/create",
        data=_create_form(name="My Analysis", cpu="2", memory="3Gi"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "my-analysis"
    # Create returns a ready-to-insert tile that behaves like any other.
    assert 'name="slug" value="my-analysis"' in body["tile_html"]
    assert "launch-form" in body["tile_html"]

    assert written["filename"] == "my-analysis.py"
    # The written file is a runnable marimo notebook carrying the resources.
    from app.notebook_meta import NotebookResources, parse_notebook_resources

    assert "import marimo" in written["content"]
    assert parse_notebook_resources(written["content"]) == NotebookResources(
        cpu=2, memory="3Gi"
    )


def test_create_from_template_injects_resources(secret_env, client, monkeypatch):
    """A template create fetches template.py and injects chosen resources."""
    template_src = (
        "# /// script\n"
        '# dependencies = ["marimo", "stargazer"]\n'
        "# ///\n"
        "import marimo\n"
    )
    written: dict = {}

    async def fake_fetch(_owner, _token, filename):
        # No collision for the new name; return the template for template.py.
        return template_src if filename == "template.py" else None

    async def fake_create(_owner, _token, filename, content, message=None):
        written.update(filename=filename, content=content)
        return {}

    monkeypatch.setattr("app.admin_app.get_workspace_notebook", fake_fetch)
    monkeypatch.setattr("app.admin_app.create_workspace_notebook", fake_create)

    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post(
        "/workspace/create",
        data=_create_form(name="from tmpl", source="template", cpu="1", memory="2Gi"),
    )
    assert resp.status_code == 200

    from app.notebook_meta import NotebookResources, parse_notebook_resources

    assert written["filename"] == "from-tmpl.py"
    assert parse_notebook_resources(written["content"]) == NotebookResources(
        cpu=1, memory="2Gi"
    )


# ---------------------------------------------------------------------------
# /workspace/delete
# ---------------------------------------------------------------------------


def test_delete_requires_session(secret_env, client):
    """Unauthenticated delete is rejected with 401."""
    resp = client.post("/workspace/delete", data={"slug": "foo"})
    assert resp.status_code == 401


def test_delete_requires_optin(secret_env, client):
    """Delete without workspace saving enabled is rejected with 403."""
    _auth(client)  # logged in, not opted in
    resp = client.post("/workspace/delete", data={"slug": "foo"})
    assert resp.status_code == 403


def test_delete_rejects_seed_slug(secret_env, client):
    """Deleting a shipped seed (blank/template) is rejected with 400."""
    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post("/workspace/delete", data={"slug": "template"})
    assert resp.status_code == 400


def test_delete_removes_notebook(secret_env, client, monkeypatch):
    """Delete removes the file from the fork and reports the slug."""
    deleted: dict = {}

    async def fake_delete(repo, token, filename, message=None):
        deleted.update(repo=repo, filename=filename)
        return True

    monkeypatch.setattr(
        "app.admin_app.delete_workspace_notebook", fake_delete, raising=False
    )
    _stub_app_get(monkeypatch, {})  # no running pod to deactivate
    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post(
        "/workspace/delete",
        data={"slug": "my-analysis"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "my-analysis"
    assert deleted == {"repo": "octocat/stargazer", "filename": "my-analysis.py"}


def test_delete_tears_down_pod_deployment(secret_env, client, monkeypatch):
    """Delete deactivates AND deletes the deployment for each running mode."""
    deactivated: list = []
    deleted_apps: list = []

    class _RunningApp:
        def __init__(self, name):
            self.name = name
            self.deactivate = SimpleNamespace(aio=self._deactivate)

        async def _deactivate(self):
            deactivated.append(self.name)

    table = {
        "nb-my-analysis-edit": _RunningApp("nb-my-analysis-edit"),
        "nb-my-analysis-run": _RunningApp("nb-my-analysis-run"),
    }

    async def fake_delete(repo, token, filename, message=None):
        return True

    monkeypatch.setattr(
        "app.admin_app.delete_workspace_notebook", fake_delete, raising=False
    )
    _stub_app_get(monkeypatch, table, deleted=deleted_apps)
    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post(
        "/workspace/delete",
        data={"slug": "my-analysis"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert sorted(deactivated) == ["nb-my-analysis-edit", "nb-my-analysis-run"]
    assert sorted(deleted_apps) == ["nb-my-analysis-edit", "nb-my-analysis-run"]


def test_delete_idempotent_when_missing(secret_env, client, monkeypatch):
    """Deleting a notebook absent from the fork still succeeds (idempotent)."""

    async def fake_delete(repo, token, filename, message=None):
        return False  # file not found on the fork

    monkeypatch.setattr(
        "app.admin_app.delete_workspace_notebook", fake_delete, raising=False
    )
    _stub_app_get(monkeypatch, {})
    _auth(client, fork_full_name="octocat/stargazer", access_token="tok")
    resp = client.post(
        "/workspace/delete",
        data={"slug": "ghost"},
        headers={"Accept": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "ghost"
