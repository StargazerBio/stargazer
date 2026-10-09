"""Tests for the dashboard: AppEnvironment, sign-in, workspace, and launch routes.

Route tests use FastAPI's `TestClient` WITHOUT the context manager so the
app's lifespan (`init()` → Flyte client) never runs. Identity is the
`X-User-*` headers Union's auth layer sets on every request; the dashboard
belongs to ALICE (its baked-in owner) and serves into her project. Workspace
routes run through the real `app.workspace_store` against a temp directory;
only control-plane calls (serve, App get/delete/list) are stubbed.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import flyte.app
import pytest
from fastapi.testclient import TestClient

from app import config, notebooks
from app import workspace_store as ws
from app.admin_app import (
    _index_url,
    _notebook_slug,
    _parse_nb_name,
    app_env,
    asgi_app,
)
from app.notebook_meta import parse_notebook_name, parse_notebook_resources

ALICE = "387300641116005877"
BOB = "111111111111111111"
PROJECT = f"u-{ALICE}"

NB_SRC = (
    "# /// script\n"
    '# dependencies = ["marimo"]\n'
    "# [tool.stargazer]\n"
    "# cpu = 4\n"
    '# memory = "8Gi"\n'
    '# name = "QC run"\n'
    '# description = "Quality control."\n'
    "# ///\n"
    "import marimo\n"
)


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    """Point the workspace store at a temp dir for every test."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", str(tmp_path / "store"))


@pytest.fixture(autouse=True)
def _owned_by_alice(monkeypatch):
    """Every test's dashboard is ALICE's, deployed into her project."""
    monkeypatch.setattr(config, "OWNER_SUBJECT", ALICE)
    monkeypatch.setattr(config, "FLYTE_PROJECT", PROJECT)


@pytest.fixture(autouse=True)
def _no_teardown(monkeypatch):
    """Pod teardown hits the control plane; make it a quiet no-op."""

    class _Missing:
        async def aio(self, **_kw):
            raise RuntimeError("not found")

    monkeypatch.setattr(
        "app.admin_app.App", SimpleNamespace(get=_Missing(), delete=_Missing())
    )


@pytest.fixture
def client():
    """A TestClient that does not trigger the app lifespan (no Flyte init)."""
    return TestClient(asgi_app, follow_redirects=False)


def _as(client: TestClient, subject: str = ALICE, name: str = "Alice Ng") -> None:
    """Sign the client in the way Union forwards identity."""
    client.headers["X-User-Subject"] = subject
    client.headers["X-User-Claim-Name"] = f'"{name}"'
    client.headers["X-User-Claim-Email"] = '"alice@example.org"'


def _put(subject: str, filename: str, src: str = NB_SRC, snapshot: bool = False):
    """Seed the store directly."""
    fn = ws.create_snapshot_notebook if snapshot else ws.create_workspace_notebook
    asyncio.run(fn(subject, filename, src))


def _get(subject: str, filename: str, snapshot: bool = False) -> str | None:
    """Read the store directly."""
    fn = ws.get_snapshot_notebook if snapshot else ws.get_workspace_notebook
    return asyncio.run(fn(subject, filename))


# ---------------------------------------------------------------------------
# AppEnvironment + deploy entrypoint
# ---------------------------------------------------------------------------


def test_the_shared_admin_deploy_is_gone():
    """Dashboards are deployed per user by `stargazer-users`, never shared."""
    from app import admin_app

    assert not hasattr(admin_app, "main")


def test_app_env_is_the_union_gated_dashboard():
    """The dashboard is gated by Union's login."""
    assert isinstance(app_env, flyte.app.AppEnvironment)
    assert app_env.name == "dashboard"
    assert app_env.requires_auth is True


def test_app_env_carries_no_github_or_session_secrets():
    """Only the asset-store credential remains in the baked env."""
    gone = {
        "GITHUB_CLIENT_ID",
        "GITHUB_CLIENT_SECRET",
        "GITHUB_APP_ID",
        "GITHUB_APP_PRIVATE_KEY",
        "GITHUB_APP_SLUG",
        "SESSION_SECRET",
        "STARGAZER_SECURE_COOKIES",
    }
    assert gone.isdisjoint(app_env.env_vars)


@pytest.mark.parametrize(
    "path",
    ["/auth/login", "/auth/callback", "/auth/logout", "/auth/app-install-callback"],
)
def test_github_login_routes_are_gone(client, path):
    """Union owns sign-in; the app's own GitHub login no longer exists."""
    _as(client)
    assert client.get(path).status_code == 404


@pytest.mark.parametrize(
    "path", ["/workspace/enable", "/workspace/save", "/workspace/pod-token"]
)
def test_fork_routes_are_gone(client, path):
    """Saving needs no opt-in, pods save themselves, and pods need no git token."""
    _as(client)
    assert client.post(path).status_code == 404


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_dashboard_requires_identity(client):
    """Without Union's identity header the dashboard 401s."""
    assert client.get("/").status_code == 401


def test_admin_sees_the_owners_dashboard(client):
    """Union is the only gate: another signed-in visitor sees the owner's tiles."""
    _put(ALICE, "qc-run.py")
    _as(client, BOB, "Bob Admin")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "qc-run" in resp.text
    assert client.get("/launch/status").status_code == 200


def test_dashboard_without_an_owner_keys_state_by_the_visitor(client, monkeypatch):
    """A local run with no baked-in owner shows the visitor's own notebooks."""
    monkeypatch.setattr(config, "OWNER_SUBJECT", "")
    _put(BOB, "bobs-nb.py")
    _put(ALICE, "alices-nb.py")
    _as(client, BOB)
    resp = client.get("/")
    assert "bobs-nb" in resp.text
    assert "alices-nb" not in resp.text


def test_health_needs_no_identity(client):
    """Health checks come from the platform, not a signed-in user."""
    assert client.get("/health").json() == {"status": "ok"}


def test_dashboard_greets_the_user_without_github(client):
    """The dashboard names the user and shows no GitHub avatar or sign-out."""
    _as(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Alice Ng" in resp.text
    assert ".png?size=" not in resp.text  # no GitHub avatar
    assert '<span class="avatar-initial">A</span>' in resp.text
    assert "/auth/logout" not in resp.text
    assert "Enable workspace saving" not in resp.text


def test_dashboard_shows_its_release_version(client, monkeypatch):
    """The version the dashboard was deployed from is on the page, for debugging."""
    monkeypatch.setattr(config, "VERSION", "18fbabe-dirty")
    _as(client)
    assert "18fbabe-dirty" in client.get("/").text


def test_dashboard_lists_only_the_users_notebooks(client):
    """Each user sees their own workspace and snapshots, never another's."""
    _put(ALICE, "qc-run.py")
    _put(ALICE, "frozen.py", snapshot=True)
    _put(BOB, "bobs-secret.py")
    _as(client)
    html = client.get("/").text
    assert "qc-run.py" in html
    assert "QC run" in html
    assert "frozen.py" in html
    assert "bobs-secret.py" not in html


def test_dashboard_without_store_says_saving_is_unavailable(client, monkeypatch):
    """A deploy with no store renders a plain notice instead of the create tile."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "")
    _as(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Saving notebooks isn't available" in resp.text
    assert 'id="create-tile"' not in resp.text


# ---------------------------------------------------------------------------
# Create / settings / delete / snapshot / copy / download
# ---------------------------------------------------------------------------


def test_create_requires_identity(client):
    """Anonymous create is refused."""
    assert client.post("/workspace/create", data={"name": "x"}).status_code == 401


def test_create_writes_a_seeded_notebook_to_the_users_store(client):
    """Create copies the blank seed under the user's key and returns its tile."""
    _as(client)
    resp = client.post("/workspace/create", data={"name": "My QC", "source": "blank"})
    assert resp.status_code == 200
    assert resp.json()["slug"] == "my-qc"
    assert "my-qc.py" in resp.json()["tile_html"]
    stored = _get(ALICE, "my-qc.py")
    assert parse_notebook_name(stored) == "My QC"
    assert "import marimo" in stored
    assert _get(BOB, "my-qc.py") is None


def test_create_from_template_uses_the_template_seed(client):
    """The template seed is a different notebook from the blank one."""
    _as(client)
    client.post("/workspace/create", data={"name": "a", "source": "blank"})
    client.post("/workspace/create", data={"name": "b", "source": "template"})
    assert "### Blank workspace notebook." in _get(ALICE, "a.py")
    assert "### Workspace template" in _get(ALICE, "b.py")


def test_create_conflict_is_409(client):
    """Creating over an existing notebook is refused."""
    _put(ALICE, "my-qc.py")
    _as(client)
    resp = client.post("/workspace/create", data={"name": "My QC"})
    assert resp.status_code == 409
    assert _get(ALICE, "my-qc.py") == NB_SRC


def test_create_rejects_reserved_name(client):
    """Seed names can't be used for user notebooks."""
    _as(client)
    assert (
        client.post("/workspace/create", data={"name": "template"}).status_code == 400
    )


def test_create_without_store_is_503(client, monkeypatch):
    """With no store configured, writes say so instead of crashing."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "")
    _as(client)
    assert client.post("/workspace/create", data={"name": "x"}).status_code == 503


def test_settings_rewrites_the_header(client):
    """Settings updates resources + description in the stored notebook."""
    _put(ALICE, "qc-run.py")
    _as(client)
    resp = client.post(
        "/workspace/settings",
        data={"slug": "qc-run", "cpu": "2", "memory": "16", "description": "New"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "slug": "qc-run",
        "cpu": 2,
        "memory": 16,
        "description": "New",
    }
    stored = _get(ALICE, "qc-run.py")
    assert parse_notebook_resources(stored).cpu == 2
    assert parse_notebook_name(stored) == "QC run"


def test_settings_missing_notebook_is_404(client):
    """Settings on a notebook the user doesn't have is a 404."""
    _put(BOB, "qc-run.py")
    _as(client)
    resp = client.post(
        "/workspace/settings", data={"slug": "qc-run", "cpu": "1", "memory": "2"}
    )
    assert resp.status_code == 404


def test_admin_acts_on_the_owners_store_not_their_own(client):
    """A visitor other than the owner reads and writes the owner's notebooks."""
    _put(ALICE, "qc-run.py")
    _as(client, BOB)
    assert client.get("/workspace/download?slug=qc-run").status_code == 200
    assert client.post("/workspace/create", data={"name": "x"}).status_code == 200
    assert _get(ALICE, "x.py") is not None
    assert _get(BOB, "x.py") is None
    assert client.post("/workspace/delete", data={"slug": "qc-run"}).status_code == 200
    assert _get(ALICE, "qc-run.py") is None


def test_delete_removes_only_the_users_notebook(client):
    """Delete removes the user's copy and leaves another user's alone."""
    _put(ALICE, "qc-run.py")
    _put(BOB, "qc-run.py")
    _as(client)
    resp = client.post("/workspace/delete", data={"slug": "qc-run"})
    assert resp.status_code == 200
    assert _get(ALICE, "qc-run.py") is None
    assert _get(BOB, "qc-run.py") == NB_SRC


def test_snapshot_moves_the_notebook(client):
    """Freezing moves a notebook from the workspace into snapshots."""
    _put(ALICE, "qc-run.py")
    _as(client)
    resp = client.post("/workspace/snapshot", data={"slug": "qc-run"})
    assert resp.status_code == 200
    assert "qc-run.py" in resp.json()["tile_html"]
    assert _get(ALICE, "qc-run.py") is None
    assert _get(ALICE, "qc-run.py", snapshot=True) == NB_SRC


def test_snapshot_delete_removes_own_snapshot(client):
    """A user's own snapshot can be deleted."""
    _put(ALICE, "frozen.py", snapshot=True)
    _as(client)
    assert client.post("/snapshot/delete", data={"slug": "frozen"}).status_code == 200
    assert _get(ALICE, "frozen.py", snapshot=True) is None


def test_copy_workflow_reads_the_shipped_notebook(client):
    """Copying a workflow writes the shipped source as an editable notebook."""
    _as(client)
    resp = client.post(
        "/workspace/copy", data={"slug": "scrna-pipeline", "section": "workflows"}
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "scrna-seq"
    stored = _get(ALICE, "scrna-seq.py")
    assert parse_notebook_name(stored) == "scRNA-seq"
    shipped = (
        Path(notebooks.NOTEBOOKS_PKG_DIR) / "workflows" / "scrna_pipeline.py"
    ).read_text()
    assert shipped.splitlines()[-1] in stored
    # A second copy would clobber the first.
    again = client.post(
        "/workspace/copy", data={"slug": "scrna-pipeline", "section": "workflows"}
    )
    assert again.status_code == 409


def test_copy_own_snapshot(client):
    """An own snapshot copies back into the workspace."""
    _put(ALICE, "frozen.py", snapshot=True)
    _as(client)
    resp = client.post(
        "/workspace/copy", data={"slug": "frozen", "section": "snapshots"}
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "qc-run"
    assert parse_notebook_name(_get(ALICE, "qc-run.py")) == "QC run"


@pytest.fixture
def public_snapshot(tmp_path, monkeypatch):
    """Ship one public snapshot `published_qc.py` in a temp snapshots dir."""
    d = tmp_path / "public"
    d.mkdir()
    (d / "__init__.py").write_text("")
    (d / "published_qc.py").write_text(NB_SRC)
    monkeypatch.setattr(notebooks, "PUBLIC_SNAPSHOTS_DIR", d)
    return d


def test_dashboard_lists_public_snapshots(client, public_snapshot):
    """Shipped snapshots show for everyone, without a delete control."""
    _as(client)
    html = client.get("/").text
    assert "published-qc.py" in html
    assert 'data-snapshot-delete-slug="published-qc"' not in html


def test_copy_public_snapshot(client, public_snapshot):
    """A shipped snapshot copies into the workspace."""
    _as(client)
    resp = client.post(
        "/workspace/copy", data={"slug": "published-qc", "section": "public-snapshots"}
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "qc-run"
    assert parse_notebook_name(_get(ALICE, "qc-run.py")) == "QC run"


def test_download_workspace_notebook(client):
    """Download returns the source as an attachment."""
    _put(ALICE, "qc-run.py")
    _as(client)
    resp = client.get("/workspace/download?slug=qc-run&section=workspace")
    assert resp.status_code == 200
    assert resp.text == NB_SRC
    assert resp.headers["content-disposition"] == 'attachment; filename="qc-run.py"'


def test_download_is_scoped_to_the_user(client):
    """One user can't download another's notebook."""
    _put(BOB, "qc-run.py")
    _as(client)
    resp = client.get("/workspace/download?slug=qc-run&section=workspace")
    assert resp.status_code == 404


def test_download_own_and_public_snapshots(client, public_snapshot):
    """Snapshots download from the store (own) or the image (public)."""
    _put(ALICE, "frozen.py", snapshot=True)
    _as(client)
    own = client.get("/workspace/download?slug=frozen&section=snapshots")
    pub = client.get("/workspace/download?slug=published-qc&section=public-snapshots")
    assert own.text == NB_SRC
    assert pub.text == NB_SRC
    assert (
        pub.headers["content-disposition"] == 'attachment; filename="published_qc.py"'
    )


# ---------------------------------------------------------------------------
# /launch
# ---------------------------------------------------------------------------


@pytest.fixture
def served(monkeypatch):
    """Capture what /launch builds and serves, without a control plane."""
    sink: dict = {}

    def fake_env(**kwargs):
        sink["kwargs"] = kwargs
        sink["env"] = SimpleNamespace(env_vars={})
        return sink["env"]

    async def fake_aio(env):
        return SimpleNamespace(endpoint="https://nb.example")

    def fake_servecontext(**kwargs):
        sink["servecontext"] = kwargs
        return SimpleNamespace(serve=SimpleNamespace(aio=fake_aio))

    monkeypatch.setattr("app.admin_app.per_notebook_env", fake_env)
    monkeypatch.setattr("flyte.with_servecontext", fake_servecontext)
    return sink


def _launch(client, slug, section, mode="edit"):
    """POST /launch as the dashboard JS does."""
    return client.post(
        "/launch",
        data={"slug": slug, "section": section, "mode": mode},
        headers={"Accept": "application/json"},
    )


def test_launch_requires_identity(client):
    """Anonymous launch is refused."""
    resp = _launch(client, "assets", "tutorials")
    assert resp.status_code == 401


def test_launch_workspace_serves_the_owners_pod(client, served):
    """A workspace launch serves the notebook from /workspace, owned by the user."""
    _put(ALICE, "qc-run.py")
    _as(client)
    resp = _launch(client, "qc-run", "workspace")
    assert resp.status_code == 200
    assert resp.json() == {"url": "https://nb.example"}
    kw = served["kwargs"]
    assert kw["notebook_path"] == "/workspace/qc-run.py"
    assert kw["owner_subject"] == ALICE
    assert kw["slug"] == "qc-run"
    assert kw["mode"] == "edit"
    assert kw["resources"].cpu == 4
    assert served["env"].env_vars == {
        "FLYTE_PROJECT": PROJECT,
        "STARGAZER_OWNER": ALICE,
    }
    assert served["servecontext"] == {"project": PROJECT, "domain": "development"}


def test_launch_tutorial_uses_the_image_path(client, served):
    """Shipped notebooks launch from the image with default resources."""
    _as(client)
    assert _launch(client, "assets", "tutorials").status_code == 200
    assert (
        served["kwargs"]["notebook_path"] == notebooks.by_slug("assets").path_in_image
    )
    assert served["kwargs"]["resources"] is None


def test_launch_own_snapshot_is_run_only(client, served):
    """Own snapshots launch read-only from /snapshots."""
    _put(ALICE, "frozen.py", snapshot=True)
    _as(client)
    assert _launch(client, "frozen", "snapshots", mode="edit").status_code == 400
    assert _launch(client, "frozen", "snapshots", mode="run").status_code == 200
    assert served["kwargs"]["notebook_path"] == "/snapshots/frozen.py"


def test_launch_public_snapshot_uses_the_image_path(client, served, public_snapshot):
    """Shipped snapshots launch from their path in the image."""
    _as(client)
    assert (
        _launch(client, "published-qc", "public-snapshots", mode="run").status_code
        == 200
    )
    assert served["kwargs"]["notebook_path"] == (
        f"{notebooks.IMAGE_WORKDIR}/src/stargazer/notebooks/snapshots/published_qc.py"
    )


# ---------------------------------------------------------------------------
# /launch/status, /stop, /workspace/cleanup
# ---------------------------------------------------------------------------


class _FakeApp:
    """Stand-in for a flyte.remote.App in status tests."""

    def __init__(self, active: bool, endpoint: str, deactivated: bool = False):
        self._active, self._endpoint, self._deactivated = active, endpoint, deactivated

    def is_active(self) -> bool:
        """Whether the app is deployed and active."""
        return self._active

    def is_deactivated(self) -> bool:
        """Whether the app has been stopped."""
        return self._deactivated

    @property
    def endpoint(self) -> str:
        """The app's public endpoint URL."""
        return self._endpoint


def _stub_apps(monkeypatch, table: dict, deleted: list | None = None):
    """Resolve App.get from `table` and list the project as its keys."""

    class _Get:
        async def aio(self, name, project, domain):
            assert project == PROJECT
            if name in table:
                return table[name]
            raise RuntimeError("not found")

    class _Delete:
        async def aio(self, name, project, domain):
            if deleted is not None:
                deleted.append(name)

    async def fake_list(project, domain="development", limit=500):
        assert project == PROJECT
        return [SimpleNamespace(name=n) for n in table]

    monkeypatch.setattr(
        "app.admin_app.App", SimpleNamespace(get=_Get(), delete=_Delete())
    )
    monkeypatch.setattr("app.admin_app.list_project_apps", fake_list)


def test_launch_status_returns_plain_endpoints(client, monkeypatch):
    """Running notebooks report their endpoint with no handoff token."""
    _stub_apps(
        monkeypatch,
        {
            "nb-assets-edit": _FakeApp(True, "https://nb.example"),
            "nb-qc-run-run": _FakeApp(False, "https://stopped.example"),
            "other-service": _FakeApp(True, "https://other.example"),
        },
    )
    _as(client)
    resp = client.get("/launch/status")
    assert resp.json() == {
        "running": [{"slug": "assets", "mode": "edit", "url": "https://nb.example"}]
    }


def test_launch_status_requires_identity(client):
    """Anonymous status is refused."""
    assert client.get("/launch/status").status_code == 401


def test_cleanup_deletes_only_stopped_notebook_apps(client, monkeypatch):
    """Cleanup removes deactivated nb-* deployments and nothing else."""
    deleted: list = []
    _stub_apps(
        monkeypatch,
        {
            "nb-old-edit": _FakeApp(False, "", deactivated=True),
            "nb-live-run": _FakeApp(True, "https://x"),
            "other-service": _FakeApp(False, "", deactivated=True),
        },
        deleted,
    )
    _as(client)
    resp = client.post("/workspace/cleanup")
    assert resp.json() == {"deleted": ["nb-old-edit"], "count": 1}
    assert deleted == ["nb-old-edit"]


def test_stop_requires_identity(client):
    """Anonymous stop is refused."""
    assert client.post("/stop", data={"slug": "a", "mode": "edit"}).status_code == 401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_parse_nb_name_roundtrips_dashed_slugs():
    """The mode is the last segment, so dashed slugs survive."""
    assert _parse_nb_name("nb-scrna-pipeline-edit") == ("scrna-pipeline", "edit")
    assert _parse_nb_name("nb-x-bogus") is None
    assert _parse_nb_name("other") is None


@pytest.mark.parametrize(
    ("name", "slug"),
    [("pr_verify", "pr-verify"), ("QC v1.2", "qc-v1-2"), ("a__b..c", "a-b-c")],
)
def test_created_notebook_slug_is_a_launchable_app_name(name, slug):
    """A notebook slug must survive Flyte's app-name rules, or it can't launch."""
    assert _notebook_slug(name) == slug
    env = flyte.app.AppEnvironment(name=f"nb-{_notebook_slug(name)}-edit", image="img")
    assert env.name == f"nb-{slug}-edit"


def test_index_url_uses_the_platform_pattern(monkeypatch):
    """Inside an app pod the in-cluster pattern names the dashboard."""
    monkeypatch.setenv(
        "INTERNAL_APP_ENDPOINT_PATTERN",
        "http://{app_fqdn}.u-jane-development.svc.cluster.local",
    )
    assert _index_url() == "http://dashboard.u-jane-development.svc.cluster.local"


def test_index_url_without_the_pattern(monkeypatch):
    """Elsewhere it's built from the dashboard's project and domain."""
    monkeypatch.delenv("INTERNAL_APP_ENDPOINT_PATTERN", raising=False)
    monkeypatch.setattr(config, "FLYTE_PROJECT", "u-jane")
    monkeypatch.setattr(config, "FLYTE_DOMAIN", "production")
    assert _index_url() == "http://dashboard.u-jane-production.svc.cluster.local"


def test_index_routes_are_mounted(client, tmp_path, monkeypatch):
    """The dashboard serves its index without needing a signed-in user."""
    from app import index_api
    from stargazer.utils.index import SqliteIndex

    monkeypatch.setattr(index_api, "_index", SqliteIndex(tmp_path / "i.db"))
    resp = client.post("/index/query", json={"filters": {}})
    assert resp.status_code == 200
    assert resp.json() == []


def test_dashboard_launcher_ships_in_the_code_bundle():
    """The startup module must be bundled: nothing the deployer imports pulls it in.

    The bundle's `app/` lands in the pod's working directory and shadows the
    installed package, so a module missing from it can't be imported at all.
    """
    assert app_env.args == ["exec", "python", "-m", "app.dashboard_launch"]
    assert "dashboard_launch.py" in app_env.include
