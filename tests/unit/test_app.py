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

import flyte
import flyte.app
import flyte.errors
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
from app.notebook_meta import (
    notebook_description,
    notebook_name,
    notebook_resources,
    setup_body,
)
from stargazer.notebooks import notebook_image_base

ALICE = "387300641116005877"
BOB = "111111111111111111"
PROJECT = f"u-{ALICE}"

NB_BODY = (
    "import flyte\n"
    "\n"
    'main_name = "QC run"\n'
    'main_description = "Quality control."\n'
    'main_resources = flyte.Resources(cpu=4, memory="8Gi")\n'
)

NB_SETUP = "with app.setup:\n" + "".join(
    f"    {line}" if line.strip() else line
    for line in NB_BODY.splitlines(keepends=True)
)

NB_SRC = (
    "# /// script\n"
    '# dependencies = ["marimo"]\n'
    "# ///\n"
    "import marimo\n\n"
    "app = marimo.App()\n\n"
    f"{NB_SETUP}"
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


def _put(subject: str, filename: str, src: str = NB_SRC):
    """Seed the store directly."""
    asyncio.run(ws.create_workspace_notebook(subject, filename, src))


def _get(subject: str, filename: str) -> str | None:
    """Read the store directly."""
    return asyncio.run(ws.get_workspace_notebook(subject, filename))


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


@pytest.mark.parametrize("path", ["/workspace/snapshot", "/snapshot/delete"])
def test_snapshot_routes_are_gone(client, path):
    """Snapshots are gone: a notebook stays in the workspace until it's published."""
    _as(client)
    assert client.post(path, data={"slug": "qc-run"}).status_code == 404


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


def test_home_page_carries_the_asset_browser(client, monkeypatch):
    """The asset browser is on the dashboard's home page, below the notebook
    sections: graph and list, both networks, and the upload panel."""
    monkeypatch.setenv("PINATA_JWT", "test-jwt")
    _as(client)
    html = client.get("/").text
    assert html.index("Tutorials") < html.index('id="graph-host"')
    assert 'data-network="private"' in html
    assert 'data-view="list"' in html
    assert 'id="upload-panel"' in html
    assert 'value="public"' in html
    # The page knows who's looking: it drives which public records they can edit.
    assert f'USERNAME = "{ALICE}"' in html


def test_home_page_without_a_pinata_key_offers_only_private_data(client, monkeypatch):
    """With no shared key the Public tab says so, without naming the service."""
    monkeypatch.delenv("PINATA_JWT", raising=False)
    _as(client)
    html = client.get("/").text
    assert 'data-network="private"' in html
    assert 'value="public"' not in html
    assert "Shared data isn't available on this deployment." in html
    assert "PINATA" not in html


def test_home_page_with_public_assets_off_offers_only_private_data(client, monkeypatch):
    """A deploy that turns public assets off hides them though it has a key."""
    monkeypatch.setenv("PINATA_JWT", "test-jwt")
    monkeypatch.setattr(config, "PUBLIC_ASSETS", False)
    _as(client)
    html = client.get("/").text
    assert 'data-network="private"' in html
    assert 'value="public"' not in html
    assert "Shared data isn't available on this deployment." in html


def test_the_upload_warning_shows_once(client):
    """The alpha note is on the page once, not again inside the upload panel."""
    _as(client)
    assert client.get("/").text.count("Stargazer is alpha software.") == 1


def test_the_separate_asset_page_is_gone(client):
    """No /assets page, and no link to it in the avatar menu."""
    _as(client)
    assert client.get("/assets").status_code == 404
    assert 'href="/assets"' not in client.get("/").text


def test_dashboard_lists_only_the_users_notebooks(client):
    """Each user sees their own workspace, never another's."""
    _put(ALICE, "qc-run.py")
    _put(BOB, "bobs-secret.py")
    _as(client)
    html = client.get("/").text
    assert "qc-run.py" in html
    assert "QC run" in html
    assert "bobs-secret.py" not in html


def test_dashboard_states_the_workspace_file_limit(client):
    """The Workspace section says which files are kept, in product terms."""
    _as(client)
    text = " ".join(client.get("/").text.split())
    assert "up to 100 MB each; store bigger files as assets." in text


def test_dashboard_warns_against_sensitive_data(client):
    """Isolation between users is soft for now, so the dashboard says so."""
    _as(client)
    assert (
        "Stargazer is alpha software. Don't upload sensitive data, such as "
        "identifiable patient data." in client.get("/").text
    )


def test_dashboard_links_to_its_projects_runs_in_the_console(client, monkeypatch):
    """On Union the dashboard links to its own project's runs, not the console root."""
    monkeypatch.setattr(
        config, "CONSOLE_URL", "https://stargazerbio.us-west-2.unionai.cloud"
    )
    monkeypatch.setattr(config, "FLYTE_PROJECT", "u-jane")
    monkeypatch.setattr(config, "FLYTE_DOMAIN", "development")
    _as(client)
    html = client.get("/").text
    href = (
        "https://stargazerbio.us-west-2.unionai.cloud"
        "/v2/domain/development/project/u-jane/runs"
    )
    assert f'href="{href}"' in html
    assert "View your runs in the Union console" in html


def test_dashboard_without_a_console_has_no_console_link(client, monkeypatch):
    """Off Union there's no console to send users to, so no link."""
    monkeypatch.setattr(config, "CONSOLE_URL", "")
    _as(client)
    html = client.get("/").text
    assert "Union console" not in html
    assert "/v2/domain/" not in html


@pytest.mark.parametrize(
    "endpoint",
    [
        "stargazerbio.us-west-2.unionai.cloud",
        "dns:///stargazerbio.us-west-2.unionai.cloud",
    ],
)
def test_console_url_comes_from_the_pods_platform_endpoint(endpoint):
    """An app pod on Union is given the tenant's endpoint; the console is its host."""
    env = {"STARGAZER_TARGET": "union", "_U_EP_OVERRIDE": endpoint}
    assert config.console_url(env) == "https://stargazerbio.us-west-2.unionai.cloud"


def test_console_url_is_empty_off_union():
    """The devbox's endpoint is an in-cluster address, not a console to link to."""
    env = {
        "STARGAZER_TARGET": "devbox",
        "_U_EP_OVERRIDE": "flyte-binary-http.flyte:8090",
    }
    assert config.console_url(env) == ""
    assert config.console_url({"STARGAZER_TARGET": "union"}) == ""


def test_dashboard_without_store_says_saving_is_unavailable(client, monkeypatch):
    """A deploy with no store renders a plain notice instead of the create tile."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "")
    _as(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Saving notebooks isn't available" in resp.text
    assert 'id="create-tile"' not in resp.text


# ---------------------------------------------------------------------------
# Create / setup / delete / copy / download
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
    assert notebook_name(stored) == "My QC"
    assert "import marimo" in stored
    assert _get(BOB, "my-qc.py") is None


def test_create_from_basic_uses_the_basic_template(client):
    """The basic template is a different notebook from the blank one."""
    _as(client)
    client.post("/workspace/create", data={"name": "a", "source": "blank"})
    client.post("/workspace/create", data={"name": "b", "source": "basic"})
    assert "### Blank workspace notebook." in _get(ALICE, "a.py")
    assert "### Basic template" in _get(ALICE, "b.py")


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
    assert client.post("/workspace/create", data={"name": "basic"}).status_code == 400


def test_create_takes_the_longest_name_that_launches(client):
    """A 22-character name makes `nb-<slug>-edit` exactly Flyte's 30."""
    _as(client)
    resp = client.post("/workspace/create", data={"name": "interval probe 2026101"})
    assert resp.status_code == 200
    assert resp.json()["slug"] == "interval-probe-2026101"


def test_create_refuses_a_name_too_long_to_launch(client):
    """One character more and the notebook's app could never be deployed."""
    _as(client)
    resp = client.post("/workspace/create", data={"name": "interval probe 20261018"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "Notebook names can be at most 22 characters."
    assert _get(ALICE, "interval-probe-20261018.py") is None


def test_create_without_store_is_503(client, monkeypatch):
    """With no store configured, writes say so instead of crashing."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "")
    _as(client)
    assert client.post("/workspace/create", data={"name": "x"}).status_code == 503


def test_setup_shows_the_notebooks_setup_block(client):
    """The gear's editor opens on the stored notebook's setup block, flush left."""
    _put(ALICE, "qc-run.py")
    _as(client)
    resp = client.get("/workspace/setup?slug=qc-run")
    assert resp.status_code == 200
    assert resp.json() == {"slug": "qc-run", "setup": NB_BODY}


def test_setup_save_rewrites_the_block_and_retitles_the_tile(client):
    """Saving writes the edited block and returns what the tile shows."""
    _put(ALICE, "qc-run.py")
    _as(client)
    body = NB_BODY.replace("cpu=4", "cpu=2").replace("Quality control.", "New")
    resp = client.post("/workspace/setup", data={"slug": "qc-run", "setup": body})
    assert resp.status_code == 200
    assert resp.json() == {"slug": "qc-run", "title": "QC run", "description": "New"}
    stored = _get(ALICE, "qc-run.py")
    assert setup_body(stored) == body
    assert notebook_resources(stored) == flyte.Resources(cpu=2, memory="8Gi")


def test_setup_save_takes_the_browsers_line_endings(client):
    """A textarea posts CRLF; the stored notebook keeps LF."""
    _put(ALICE, "qc-run.py")
    _as(client)
    body = NB_BODY.replace("\n", "\r\n")
    resp = client.post("/workspace/setup", data={"slug": "qc-run", "setup": body})
    assert resp.status_code == 200
    assert _get(ALICE, "qc-run.py") == NB_SRC


def test_setup_save_refuses_a_broken_block(client):
    """A block that won't parse is a 400 with the reason; nothing is written."""
    _put(ALICE, "qc-run.py")
    _as(client)
    resp = client.post(
        "/workspace/setup",
        data={"slug": "qc-run", "setup": "import flyte\nmain_name = (\n"},
    )
    assert resp.status_code == 400
    assert "line 2" in resp.json()["error"]
    assert _get(ALICE, "qc-run.py") == NB_SRC


def test_setup_missing_notebook_is_404(client):
    """The setup block of a notebook the user doesn't have is a 404."""
    _put(BOB, "qc-run.py")
    _as(client)
    assert client.get("/workspace/setup?slug=qc-run").status_code == 404
    resp = client.post("/workspace/setup", data={"slug": "qc-run", "setup": NB_BODY})
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


def test_copy_workflow_reads_the_shipped_notebook(client):
    """Copying a workflow writes the shipped source as an editable notebook."""
    _as(client)
    resp = client.post(
        "/workspace/copy", data={"slug": "scrna-pipeline", "section": "workflows"}
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "scrna-seq"
    stored = _get(ALICE, "scrna-seq.py")
    assert notebook_name(stored) == "scRNA-seq"
    assert (
        notebook_description(stored) == notebooks.by_slug("scrna-pipeline").description
    )
    shipped = (
        Path(notebooks.NOTEBOOKS_PKG_DIR) / "workflows" / "scrna_pipeline.py"
    ).read_text()
    assert shipped.splitlines()[-1] in stored
    # A second copy would clobber the first.
    again = client.post(
        "/workspace/copy", data={"slug": "scrna-pipeline", "section": "workflows"}
    )
    assert again.status_code == 409


def test_download_workspace_notebook(client):
    """Download returns the source as an attachment."""
    _put(ALICE, "qc-run.py")
    _as(client)
    resp = client.get("/workspace/download?slug=qc-run")
    assert resp.status_code == 200
    assert resp.text == NB_SRC
    assert resp.headers["content-disposition"] == 'attachment; filename="qc-run.py"'


def test_download_is_scoped_to_the_user(client):
    """One user can't download another's notebook."""
    _put(BOB, "qc-run.py")
    _as(client)
    resp = client.get("/workspace/download?slug=qc-run")
    assert resp.status_code == 404


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
    assert kw["resources"] == flyte.Resources(cpu=4, memory="8Gi")
    assert served["env"].env_vars == {
        "FLYTE_PROJECT": PROJECT,
        "STARGAZER_OWNER": ALICE,
        "SG_SAVE_INTERVAL_SECONDS": str(ws.DEFAULT_SETTINGS["save_interval_seconds"]),
    }
    assert served["servecontext"] == {"project": PROJECT, "domain": "development"}


def _save_settings(client, interval):
    """POST /settings as the dashboard's Settings form does."""
    return client.post(
        "/settings",
        data={"save_interval_seconds": interval},
        headers={"Accept": "application/json"},
    )


def test_saved_interval_reaches_the_next_launch(client, served):
    """The interval a user saves is the one their next notebook pod gets."""
    _put(ALICE, "qc-run.py")
    _as(client)
    assert _save_settings(client, "60").status_code == 200
    assert _launch(client, "qc-run", "workspace").status_code == 200
    assert served["env"].env_vars["SG_SAVE_INTERVAL_SECONDS"] == "60"


@pytest.mark.parametrize("bad", ["-1", "soon", "1.5", ""])
def test_bad_interval_is_refused_and_not_stored(client, bad):
    """Only a whole number of seconds, 0 or more, is saved."""
    _as(client)
    assert _save_settings(client, "60").status_code == 200
    resp = _save_settings(client, bad)
    assert resp.status_code == 400
    stored = asyncio.run(ws.get_settings(ALICE))
    assert stored["save_interval_seconds"] == 60


def test_dashboard_shows_the_saved_interval(client):
    """The Settings section shows what the user saved."""
    _as(client)
    _save_settings(client, "45")
    resp = client.get("/")
    assert 'name="save_interval_seconds"' in resp.text
    assert 'value="45"' in resp.text


def test_launch_tutorial_uses_the_image_path(client, served):
    """Shipped notebooks launch from the image with default resources."""
    _as(client)
    assert _launch(client, "assets", "tutorials").status_code == 200
    assert (
        served["kwargs"]["notebook_path"] == notebooks.by_slug("assets").path_in_image
    )
    assert served["kwargs"]["resources"] is None


IMG_SRC = (
    "import marimo\n"
    "app = marimo.App()\n"
    "with app.setup:\n"
    "    from stargazer.notebooks import notebook_base\n"
    "    main_img = notebook_base.with_apt_packages('bcftools')\n"
)


@pytest.fixture
def union(monkeypatch):
    """Launches aim at Union, where a notebook's own image can be built."""
    monkeypatch.setattr(config, "TARGET", "union")


def test_launch_without_main_img_serves_the_deployed_image(client, served):
    """A notebook that declares no image runs on the deployed one."""
    _put(ALICE, "qc-run.py")
    _as(client)
    assert _launch(client, "qc-run", "workspace").status_code == 200
    assert served["kwargs"]["image"] is None


def test_launch_serves_the_declared_image(client, served, union):
    """A declared image is handed to serve, which builds it before deploying."""
    _put(ALICE, "qc-run.py", IMG_SRC)
    _as(client)
    resp = _launch(client, "qc-run", "workspace")
    assert resp.json() == {"url": "https://nb.example"}
    assert served["kwargs"]["image"] == notebook_image_base(
        config.NOTEBOOK_IMAGE
    ).with_apt_packages("bcftools")


def test_launch_refuses_a_broken_main_img(client, served, union):
    """A `main_img` that doesn't evaluate is a launch error, not a default pod."""
    _put(ALICE, "qc-run.py", IMG_SRC.replace("'bcftools'", "*TOOLS"))
    _as(client)
    resp = _launch(client, "qc-run", "workspace")
    assert resp.status_code == 422
    assert "NameError" in resp.json()["error"]
    assert "kwargs" not in served


def test_launch_refuses_resources_it_cannot_read(client, served):
    """Resources that aren't literal are a launch error, not a default pod."""
    _put(ALICE, "qc-run.py", NB_SRC.replace("cpu=4", "cpu=CPUS"))
    _as(client)
    resp = _launch(client, "qc-run", "workspace")
    assert resp.status_code == 422
    assert "main_resources" in resp.json()["error"]
    assert "kwargs" not in served


def test_launch_refuses_when_the_image_fails_to_build(
    client, served, union, monkeypatch
):
    """A failed build never falls back to the notebook's existing pod."""

    async def failing_aio(env):
        raise flyte.errors.ImageBuildError("Build failed in 0:01:00")

    async def existing_app(**_kw):
        return SimpleNamespace(endpoint="https://old-pod.example")

    monkeypatch.setattr(
        "flyte.with_servecontext",
        lambda **_kw: SimpleNamespace(serve=SimpleNamespace(aio=failing_aio)),
    )
    monkeypatch.setattr(
        "app.admin_app.App", SimpleNamespace(get=SimpleNamespace(aio=existing_app))
    )
    _put(ALICE, "qc-run.py", IMG_SRC)
    _as(client)
    resp = _launch(client, "qc-run", "workspace")
    assert resp.status_code == 422
    assert "Build failed" in resp.json()["error"]


def test_launch_reports_why_the_app_was_never_created(client, served, monkeypatch):
    """A deploy the platform refused is a failure, not a pod still starting."""

    async def refused_aio(env):
        raise flyte.errors.DeploymentError("app.metadata.id.name: too long")

    monkeypatch.setattr(
        "flyte.with_servecontext",
        lambda **_kw: SimpleNamespace(serve=SimpleNamespace(aio=refused_aio)),
    )
    _put(ALICE, "qc-run.py")
    _as(client)
    resp = _launch(client, "qc-run", "workspace")
    assert resp.status_code == 422
    assert resp.json()["error"] == "app.metadata.id.name: too long"


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


async def _unreachable(*_args, **_kwargs):
    """A store or control-plane call that fails."""
    raise OSError("unreachable")


@pytest.mark.parametrize(
    ("path", "data", "broken", "replacement", "error"),
    [
        (
            "/workspace/create",
            {"name": "x"},
            "app.workspace_store.create_workspace_notebook",
            _unreachable,
            "create failed: unreachable",
        ),
        (
            "/workspace/copy",
            {"slug": "scrna-pipeline", "section": "workflows"},
            "app.workspace_store.create_workspace_notebook",
            _unreachable,
            "copy failed: unreachable",
        ),
        (
            "/workspace/setup",
            {"slug": "qc-run", "setup": NB_BODY},
            "app.workspace_store.update_workspace_notebook",
            _unreachable,
            "update failed: unreachable",
        ),
        (
            "/workspace/delete",
            {"slug": "qc-run"},
            "app.workspace_store.delete_workspace_notebook",
            _unreachable,
            "delete failed: unreachable",
        ),
        (
            "/stop",
            {"slug": "qc-run", "mode": "edit"},
            "app.admin_app.App",
            SimpleNamespace(get=SimpleNamespace(aio=_unreachable)),
            "stop failed: unreachable",
        ),
        (
            "/workspace/cleanup",
            {},
            "app.admin_app.list_project_apps",
            _unreachable,
            "cleanup failed: unreachable",
        ),
    ],
)
def test_a_failed_action_is_a_500_with_its_reason(
    client, monkeypatch, path, data, broken, replacement, error
):
    """Not a 502: Cloudflare, in front of Union apps, replaces a 502's body."""
    _put(ALICE, "qc-run.py")
    monkeypatch.setattr(broken, replacement)
    _as(client)
    resp = client.post(path, data=data)
    assert resp.status_code == 500
    assert resp.json() == {"error": error}


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


def test_index_url_passes_on_a_postgres_index(monkeypatch):
    """A dashboard on a Postgres index hands pods that index, not its address."""
    url = "postgresql://sg:pw@postgres.stargazer.svc.cluster.local:5432/stargazer"
    monkeypatch.setenv("STARGAZER_INDEX_URL", url)
    monkeypatch.setenv(
        "INTERNAL_APP_ENDPOINT_PATTERN",
        "http://{app_fqdn}.u-jane-development.svc.cluster.local",
    )
    assert _index_url() == url


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
