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
import httpx
import pytest
from fastapi.testclient import TestClient
from flyte._build import ImageBuild
from flyte._environment import list_loaded_environments
from flyte._internal.imagebuild import image_builder
from flyte._internal.imagebuild.image_builder import ImageBuildEngine

from app import admin_app, config, notebooks
from app import workspace_store as ws
from app.admin_app import (
    _new_notebook_slug,
    _notebook_slug,
    _parse_nb_name,
    app_env,
    asgi_app,
)
from app.notebook_environment import evaluate_main_env, extract_main_env
from app.notebook_meta import notebook_description, notebook_name, setup_body
from stargazer.notebooks import notebook_image_base

ALICE = "387300641116005877"
BOB = "111111111111111111"
PROJECT = f"u-{ALICE}"

pytestmark = pytest.mark.usefixtures("workspace_root")

NB_BODY = (
    "import flyte\n"
    "\n"
    "from stargazer.notebooks import notebook_env\n"
    "\n"
    'main_name = "QC run"\n'
    'main_description = "Quality control."\n'
    'main_env = notebook_env.clone_with(name="qc", resources=flyte.Resources(cpu=4, memory="8Gi"))\n'
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


def test_app_env_is_the_union_gated_dashboard():
    """The dashboard is gated by Union's login."""
    assert isinstance(app_env, flyte.app.AppEnvironment)
    assert app_env.name == "dashboard"
    assert app_env.requires_auth is True


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
    # The asset browser compares records' owners against the visitor, not the owner.
    assert f'USERNAME = "{BOB}"' in resp.text
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


def test_dashboard_greets_the_user(client):
    """The dashboard names the user and shows their initial."""
    _as(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Alice Ng" in resp.text
    assert '<span class="avatar-initial">A</span>' in resp.text


def test_dashboard_shows_its_release_version(client, monkeypatch):
    """The version the dashboard was deployed from is on the page, for debugging."""
    monkeypatch.setattr(config, "VERSION", "18fbabe-dirty")
    _as(client)
    assert "18fbabe-dirty" in client.get("/").text


def test_home_page_carries_the_asset_browser(client, monkeypatch):
    """The asset browser is on the dashboard's home page, below the workspace:
    graph and list, every source, and the upload panel. It starts on the
    user's assets and the shipped notebooks."""
    monkeypatch.setenv("PINATA_JWT", "test-jwt")
    _as(client)
    html = client.get("/").text
    assert html.index('id="workspace-grid"') < html.index('id="graph-host"')
    assert '<button data-source="mine" aria-pressed="true">' in html
    assert '<button data-source="public" aria-pressed="false">' in html
    assert '<button data-source="stargazer" aria-pressed="true">' in html
    assert 'data-view="list"' in html
    assert 'id="upload-panel"' in html
    assert 'value="public"' in html
    # The page knows who's looking: it drives which public records they can edit.
    assert f'USERNAME = "{ALICE}"' in html


def test_shipped_notebooks_have_no_section_of_their_own(client):
    """Tutorials and Workflows are explorer entries, not tiles on the page."""
    _as(client)
    html = client.get("/").text
    assert 'name="section" value="tutorials"' not in html
    assert 'name="section" value="workflows"' not in html
    assert 'data-copy-section="workflows"' not in html


@pytest.mark.parametrize(
    ("jwt", "public_assets"), [(None, True), ("test-jwt", False)], ids=["no-key", "off"]
)
def test_home_page_without_public_assets_offers_only_private_data(
    client, monkeypatch, jwt, public_assets
):
    """With no shared key, or public assets off, Public isn't offered.

    Neither as a source nor as an upload's network, and the page doesn't
    name the service.
    """
    if jwt is None:
        monkeypatch.delenv("PINATA_JWT", raising=False)
    else:
        monkeypatch.setenv("PINATA_JWT", jwt)
    monkeypatch.setattr(config, "PUBLIC_ASSETS", public_assets)
    _as(client)
    html = client.get("/").text
    assert 'data-source="mine"' in html
    assert 'data-source="public"' not in html
    assert 'value="public"' not in html
    assert "PINATA" not in html


def test_the_alpha_warning_shows_once(client):
    """The alpha note is on the page once, not again inside the upload panel.

    Isolation between users is soft for now, so it warns against sensitive data.
    """
    _as(client)
    warning = (
        "Stargazer is alpha software. Don't upload sensitive data, such as "
        "identifiable patient data."
    )
    assert client.get("/").text.count(warning) == 1


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
    assert "View your runs" in html


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


def test_create_refuses_a_builtin_notebooks_name(client):
    """A workspace notebook can't take a built-in notebook's slug, and its app."""
    _as(client)
    resp = client.post("/workspace/create", data={"name": "Assets"})
    assert resp.status_code == 400
    assert resp.json()["error"] == (
        '"Assets" is taken by a built-in notebook. Pick another name.'
    )
    assert _get(ALICE, "assets.py") is None


@pytest.mark.parametrize("nb", notebooks.NOTEBOOKS, ids=lambda nb: nb.slug)
def test_every_builtin_slug_is_reserved(nb):
    """Every built-in notebook's slug is refused as a workspace notebook's."""
    assert _new_notebook_slug(nb.slug) is None


def test_a_stored_notebook_under_a_builtin_slug_stays_manageable(client):
    """One saved before built-in names were reserved can still be downloaded and deleted."""
    _put(ALICE, "assets.py")
    _as(client)
    assert client.get("/workspace/download?slug=assets").text == NB_SRC
    assert client.post("/workspace/delete", data={"slug": "assets"}).status_code == 200
    assert _get(ALICE, "assets.py") is None


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
    assert evaluate_main_env(extract_main_env(stored)).resources == flyte.Resources(
        cpu=2, memory="8Gi"
    )


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


def test_setup_save_refuses_an_environment_it_cannot_serve(client):
    """A `main_env` that won't evaluate is a 400 with the reason; nothing is written."""
    _put(ALICE, "qc-run.py")
    _as(client)
    body = NB_BODY.replace("cpu=4", "cpu=CPUS")
    resp = client.post("/workspace/setup", data={"slug": "qc-run", "setup": body})
    assert resp.status_code == 400
    assert "NameError" in resp.json()["error"]
    assert _get(ALICE, "qc-run.py") == NB_SRC


@pytest.mark.parametrize("mode", ["edit", "run"])
def test_setup_save_refuses_while_the_notebook_runs(client, monkeypatch, mode):
    """A running pod would save its own copy over the gear's; the save is a 409."""
    _stub_apps(monkeypatch, {f"nb-qc-run-{mode}": _FakeApp(True, "")})
    _put(ALICE, "qc-run.py")
    _as(client)
    body = NB_BODY.replace("cpu=4", "cpu=2")
    resp = client.post("/workspace/setup", data={"slug": "qc-run", "setup": body})
    assert resp.status_code == 409
    assert "Stop the notebook" in resp.json()["error"]
    assert _get(ALICE, "qc-run.py") == NB_SRC


def test_setup_save_goes_through_once_the_notebook_is_stopped(client, monkeypatch):
    """A stopped notebook's deployment doesn't hold the gear back."""
    _stub_apps(
        monkeypatch,
        {
            "nb-qc-run-edit": _FakeApp(False, "", deactivated=True),
            "nb-other-edit": _FakeApp(True, "https://other.example"),
        },
    )
    _put(ALICE, "qc-run.py")
    _as(client)
    body = NB_BODY.replace("cpu=4", "cpu=2")
    resp = client.post("/workspace/setup", data={"slug": "qc-run", "setup": body})
    assert resp.status_code == 200
    assert setup_body(_get(ALICE, "qc-run.py")) == body


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


def test_copy_workflow_reads_the_builtin_notebook(client):
    """Copying a workflow writes the built-in source as an editable notebook."""
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
    builtin = (
        Path(notebooks.NOTEBOOKS_PKG_DIR) / "workflows" / "scrna_pipeline.py"
    ).read_text()
    assert builtin.splitlines()[-1] in stored
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
# /workspace/github
# ---------------------------------------------------------------------------

COMMIT = "72dd7db0a1b2c3d4e5f60718293a4b5c6d7e8f90"
RAW = "https://raw.githubusercontent.com"
BARE_NB = "import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _():\n    return\n"


@pytest.fixture
def github(monkeypatch):
    """GitHub faked at the HTTP boundary: `files` maps a raw URL to its body.

    A URL not in `files` is a 404. Returns `(files, requested)`, where
    `requested` lists every URL the dashboard fetched.
    """
    files: dict[str, bytes] = {}
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        if url in files:
            return httpx.Response(200, content=files[url])
        return httpx.Response(404, content=b"404: Not Found")

    monkeypatch.setattr("app.github_import.TRANSPORT", httpx.MockTransport(handler))
    return files, requested


def _open_github(client, link):
    """POST a GitHub link to the open-from-GitHub action."""
    return client.post("/workspace/github", data={"link": link})


def test_github_blob_link_opens_the_file_as_a_workspace_notebook(client, github):
    """A github.com file link pinned to a commit lands as a workspace notebook."""
    files, requested = github
    files[f"{RAW}/someone/repo/{COMMIT}/notebooks/qc.py"] = NB_SRC.encode()
    _as(client)
    resp = _open_github(
        client, f"https://github.com/someone/repo/blob/{COMMIT}/notebooks/qc.py"
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "qc-run"
    assert "QC run" in resp.json()["tile_html"]
    assert requested == [f"{RAW}/someone/repo/{COMMIT}/notebooks/qc.py"]
    assert _get(ALICE, "qc-run.py") == NB_SRC


def test_github_raw_link_names_an_unnamed_notebook_after_its_file(client, github):
    """A raw link works too, and a notebook with no name tiles as its file name."""
    files, _ = github
    files[f"{RAW}/someone/repo/{COMMIT}/my_analysis.py"] = BARE_NB.encode()
    _as(client)
    resp = _open_github(client, f"{RAW}/someone/repo/{COMMIT}/my_analysis.py")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "my-analysis"
    stored = _get(ALICE, "my-analysis.py")
    assert notebook_name(stored) == "my_analysis"
    assert stored.endswith("@app.cell\ndef _():\n    return\n")


def test_github_name_taken_is_409(client, github):
    """Opening a notebook whose name is taken refuses, like copy."""
    files, _ = github
    files[f"{RAW}/someone/repo/{COMMIT}/qc.py"] = NB_SRC.encode()
    _put(ALICE, "qc-run.py", "untouched")
    _as(client)
    resp = _open_github(client, f"{RAW}/someone/repo/{COMMIT}/qc.py")
    assert resp.status_code == 409
    assert _get(ALICE, "qc-run.py") == "untouched"


def test_github_refuses_a_builtin_notebooks_name(client, github):
    """A file named like a built-in notebook isn't opened under its slug."""
    files, _ = github
    files[f"{RAW}/someone/repo/{COMMIT}/assets.py"] = BARE_NB.encode()
    _as(client)
    resp = _open_github(client, f"{RAW}/someone/repo/{COMMIT}/assets.py")
    assert resp.status_code == 409
    assert resp.json()["error"] == '"assets" is taken by a built-in notebook.'
    assert _get(ALICE, "assets.py") is None


@pytest.mark.parametrize(
    "link",
    [
        f"https://gitlab.com/someone/repo/blob/{COMMIT}/qc.py",
        f"https://github.com.evil.example/someone/repo/blob/{COMMIT}/qc.py",
        f"https://github.com/someone/repo/tree/{COMMIT}/notebooks",
        f"https://github.com/someone/repo/blob/{COMMIT}/README.md",
        "https://github.com/someone/repo",
        "not a link",
    ],
)
def test_github_refuses_a_link_that_is_not_a_python_file_on_github(
    client, github, link
):
    """Anything but a .py file link on GitHub is refused without fetching."""
    _, requested = github
    _as(client)
    resp = _open_github(client, link)
    assert resp.status_code == 400
    assert "link to a .py file on GitHub" in resp.json()["error"]
    assert requested == []


def test_github_missing_file_says_so(client, github):
    """A link to a file GitHub doesn't have is a 404 that says so."""
    _as(client)
    resp = _open_github(client, f"{RAW}/someone/repo/{COMMIT}/gone.py")
    assert resp.status_code == 404
    assert "wasn't found on GitHub" in resp.json()["error"]


def test_github_file_too_big_is_refused(client, github, monkeypatch):
    """A file over the size cap is refused and nothing is written."""
    files, _ = github
    monkeypatch.setattr("app.github_import.MAX_BYTES", 100)
    files[f"{RAW}/someone/repo/{COMMIT}/big.py"] = BARE_NB.encode() + b"#" * 200
    _as(client)
    resp = _open_github(client, f"{RAW}/someone/repo/{COMMIT}/big.py")
    assert resp.status_code == 413
    assert "too big" in resp.json()["error"]
    assert _get(ALICE, "big.py") is None


def test_github_file_that_is_not_a_notebook_is_refused(client, github):
    """A Python file that isn't a marimo notebook is refused."""
    files, _ = github
    files[f"{RAW}/someone/repo/{COMMIT}/script.py"] = b"print('hi')\n"
    _as(client)
    resp = _open_github(client, f"{RAW}/someone/repo/{COMMIT}/script.py")
    assert resp.status_code == 400
    assert "isn't a marimo notebook" in resp.json()["error"]
    assert _get(ALICE, "script.py") is None


# ---------------------------------------------------------------------------
# /launch
# ---------------------------------------------------------------------------


class _FakeBuildRun:
    """A remote image build run that the test finishes by hand."""

    def __init__(self, builder: _FakeBuilder, n: int):
        self.url = f"https://console.example/runs/build-{n}"
        self._builder = builder
        self._done = asyncio.Event()
        self._ok = False
        self.wait = SimpleNamespace(aio=self._wait)
        self.raise_for_status = SimpleNamespace(aio=self._raise_for_status)

    async def _wait(self, quiet: bool = False):
        await self._done.wait()

    async def _raise_for_status(self):
        if not self._ok:
            raise flyte.errors.RuntimeUserError("BuildFailed", f"{self.url} failed")

    def finish(self, ok: bool = True):
        """End the build; a successful one puts the image in the registry."""
        self._ok = ok
        self._builder.built = self._builder.built or ok
        self._done.set()


class _FakeBuilder:
    """The remote image builder: a registry check and build runs, no network."""

    def __init__(self):
        self.built = True
        self.runs: list[_FakeBuildRun] = []
        builder = self

        class _Checker:
            @classmethod
            async def image_exists(cls, repository, tag, arch):
                return f"registry.example/{repository}:{tag}" if builder.built else None

        self._checker = _Checker

    def get_checkers(self):
        """The registry check `ImageBuildEngine.image_exists` runs."""
        return [self._checker]

    async def build_image(self, image, dry_run=False, wait=True, force=False):
        """Submit a build run; wait for it unless `wait` is False."""
        run = _FakeBuildRun(self, len(self.runs) + 1)
        self.runs.append(run)
        if wait:
            await run.wait.aio()
            await run.raise_for_status.aio()
            return ImageBuild(uri=f"registry.example/{image.name}", remote_run=run)
        return ImageBuild(uri=None, remote_run=run)


@pytest.fixture
def builder(monkeypatch):
    """Route Flyte's real image build engine (and its caches) to `_FakeBuilder`."""
    fake = _FakeBuilder()
    monkeypatch.setattr(image_builder, "_builds_locally", lambda _builder: False)
    monkeypatch.setattr(
        ImageBuildEngine, "_get_builder", classmethod(lambda cls, _b=None: fake)
    )
    ImageBuildEngine.image_exists.cache_clear()
    ImageBuildEngine.build.cache_clear()
    yield fake
    ImageBuildEngine.image_exists.cache_clear()
    ImageBuildEngine.build.cache_clear()


@pytest.fixture
def served(monkeypatch, builder):
    """Capture what /launch builds and serves, without a control plane."""
    sink: dict = {"served": 0}

    def fake_env(**kwargs):
        sink["kwargs"] = kwargs
        declared = kwargs["declared"]
        sink["env"] = SimpleNamespace(
            env_vars={}, image=declared.image if declared else None
        )
        return sink["env"]

    async def fake_aio(env):
        # Like `serve`, build the image (waiting) before serving.
        if isinstance(env.image, flyte.Image):
            await flyte.build.aio(env.image)
        sink["served"] += 1
        return SimpleNamespace(endpoint="https://nb.example")

    def fake_servecontext(**kwargs):
        sink["servecontext"] = kwargs
        return SimpleNamespace(serve=SimpleNamespace(aio=fake_aio))

    monkeypatch.setattr("app.admin_app.per_notebook_env", fake_env)
    monkeypatch.setattr("flyte.with_servecontext", fake_servecontext)
    yield sink
    # A test that fails mid-build leaves its build behind; the next starts clean.
    admin_app._builds.clear()


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
    assert kw["declared"].resources == flyte.Resources(cpu=4, memory="8Gi")
    assert served["env"].env_vars == {
        "FLYTE_PROJECT": PROJECT,
        "STARGAZER_OWNER": ALICE,
        "SG_SAVE_INTERVAL_SECONDS": str(ws.DEFAULT_SETTINGS["save_interval_seconds"]),
    }
    assert served["servecontext"] == {"project": PROJECT, "domain": "development"}


def test_launch_hands_the_pod_the_dashboards_index(client, served, monkeypatch):
    """The notebook pod indexes in the owner's DSQL table, as the dashboard does."""
    url = (
        "dsql://u_jane@abc123.dsql.us-west-2.on.aws/assets.u_jane"
        "?role_arn=arn:aws:iam::111122223333:role/stargazer-index-u-jane"
    )
    monkeypatch.setenv("STARGAZER_INDEX_URL", url)
    _as(client)
    assert _launch(client, "assets", "tutorials").status_code == 200
    assert served["kwargs"]["index_url"] == url


def _save_settings(client, interval):
    """POST /settings as the dashboard's Settings modal does."""
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


def _between(text, start, end):
    """The part of `text` from `start` up to the next `end`."""
    head = text.index(start)
    return text[head : text.index(end, head)]


def test_dashboard_shows_the_saved_interval(client):
    """The header's Settings button opens a modal holding what the user saved."""
    _as(client)
    _save_settings(client, "45")
    page = client.get("/").text
    assert 'aria-controls="settings-modal"' in _between(page, "<header", "</header>")
    modal = _between(page, '<dialog id="settings-modal"', "</dialog>")
    assert 'id="user-settings-form"' in modal
    assert 'value="45"' in modal


def test_launch_tutorial_uses_the_image_path(client, served):
    """Built-in notebooks launch from the image with default resources."""
    _as(client)
    assert _launch(client, "assets", "tutorials").status_code == 200
    assert (
        served["kwargs"]["notebook_path"] == notebooks.by_slug("assets").path_in_image
    )
    assert served["kwargs"]["declared"] is None


IMG_SRC = (
    "import marimo\n"
    "app = marimo.App()\n"
    "with app.setup:\n"
    "    from stargazer.notebooks import notebook_base, notebook_env\n"
    "    main_env = notebook_env.clone_with(\n"
    "        name='qc', image=notebook_base.with_apt_packages('bcftools')\n"
    "    )\n"
)


def test_launch_without_main_env_serves_the_default_environment(client, served):
    """A notebook that declares no environment runs on `notebook_env`."""
    _put(ALICE, "qc-run.py", NB_SRC.replace("main_env", "other_env"))
    _as(client)
    assert _launch(client, "qc-run", "workspace").status_code == 200
    assert served["kwargs"]["declared"] is None


def test_launch_serves_the_declared_environment(client, served, union):
    """A declared environment is handed to serve, which builds its image first."""
    _put(ALICE, "qc-run.py", IMG_SRC)
    _as(client)
    resp = _launch(client, "qc-run", "workspace")
    assert resp.json() == {"url": "https://nb.example"}
    assert served["kwargs"]["declared"].image == notebook_image_base(
        config.NOTEBOOK_IMAGE
    ).with_apt_packages("bcftools")


def test_launch_refuses_a_broken_main_env(client, served, union):
    """A `main_env` that doesn't evaluate is a launch error, not a default pod."""
    _put(ALICE, "qc-run.py", IMG_SRC.replace("'bcftools'", "*TOOLS"))
    _as(client)
    resp = _launch(client, "qc-run", "workspace")
    assert resp.status_code == 422
    assert "NameError" in resp.json()["error"]
    assert "kwargs" not in served


def test_launch_leaves_the_environment_registry_as_it_was(client, served, union):
    """A long-lived dashboard doesn't keep every launch's environments."""
    _put(ALICE, "qc-run.py", IMG_SRC)
    _as(client)
    before = [id(env) for env in list_loaded_environments()]
    assert _launch(client, "qc-run", "workspace").status_code == 200
    assert [id(env) for env in list_loaded_environments()] == before


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


async def _alaunch(ac: httpx.AsyncClient, slug: str, mode: str = "edit"):
    """POST /launch for a workspace notebook, from inside the app's event loop.

    Bounded, since a launch that waits for an unfinished build never answers.
    """
    return await asyncio.wait_for(
        ac.post(
            "/launch",
            data={"slug": slug, "section": "workspace", "mode": mode},
            headers={"Accept": "application/json"},
        ),
        timeout=5,
    )


async def _status_once_built(ac: httpx.AsyncClient) -> dict:
    """/launch/status once no build is in progress (the background serve is done)."""
    for _ in range(200):
        status = (await ac.get("/launch/status")).json()
        if not status["building"]:
            return status
        await asyncio.sleep(0.01)
    raise AssertionError(f"still building: {status}")


@pytest.fixture
def aclient(monkeypatch):
    """An async client on the test's own loop, so background tasks keep running."""
    monkeypatch.setattr("app.admin_app.list_project_apps", _no_apps)
    _put(ALICE, "qc-run.py", IMG_SRC)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=asgi_app),
        base_url="http://dashboard.example",
        headers={
            "X-User-Subject": ALICE,
            "X-User-Claim-Name": '"Alice Ng"',
            "X-User-Claim-Email": '"alice@example.org"',
        },
    )


async def _no_apps(project, domain="development", limit=500):
    """The project has no notebook apps yet."""
    return []


async def test_launch_answers_at_once_while_the_image_builds(
    aclient, served, builder, union
):
    """An unbuilt image answers 202 with its build run; the pod is served after."""
    builder.built = False
    async with aclient as ac:
        resp = await _alaunch(ac, "qc-run")
        assert resp.status_code == 202
        assert resp.json() == {"building": "https://console.example/runs/build-1"}
        assert served["served"] == 0
        status = (await ac.get("/launch/status")).json()
        assert status["building"] == [
            {
                "slug": "qc-run",
                "mode": "edit",
                "url": "https://console.example/runs/build-1",
            }
        ]

        builder.runs[0].finish()
        await _status_once_built(ac)
        assert served["served"] == 1
        assert len(builder.runs) == 1


async def test_a_second_launch_during_the_build_starts_no_build(
    aclient, served, builder, union
):
    """Launching again mid-build answers 202 with the same build run."""
    builder.built = False
    async with aclient as ac:
        await _alaunch(ac, "qc-run")
        again = await _alaunch(ac, "qc-run")
        assert again.status_code == 202
        assert again.json() == {"building": "https://console.example/runs/build-1"}
        assert len(builder.runs) == 1
        builder.runs[0].finish()
        await _status_once_built(ac)
        assert served["served"] == 1


async def test_a_launch_after_the_build_serves_at_once(aclient, served, builder, union):
    """Once built, the next launch serves without another build."""
    builder.built = False
    async with aclient as ac:
        await _alaunch(ac, "qc-run")
        builder.runs[0].finish()
        await _status_once_built(ac)
        resp = await _alaunch(ac, "qc-run")
        assert resp.status_code == 200
        assert resp.json() == {"url": "https://nb.example"}
        assert len(builder.runs) == 1
        assert served["served"] == 2


async def test_a_failed_build_is_reported_through_status(
    aclient, served, builder, union
):
    """A failed build serves nothing and says why; the next launch builds again."""
    builder.built = False
    async with aclient as ac:
        await _alaunch(ac, "qc-run")
        builder.runs[0].finish(ok=False)
        status = await _status_once_built(ac)
        [failed] = status["failed"]
        assert (failed["slug"], failed["mode"]) == ("qc-run", "edit")
        assert "https://console.example/runs/build-1 failed" in failed["error"]
        assert served["served"] == 0

        retry = await _alaunch(ac, "qc-run")
        assert retry.json() == {"building": "https://console.example/runs/build-2"}
        assert (await ac.get("/launch/status")).json()["failed"] == []
        builder.runs[1].finish()
        await _status_once_built(ac)


async def test_an_unexpected_error_after_the_build_is_a_failure(
    aclient, served, builder, union, monkeypatch
):
    """A background serve that raises is reported failed, not building forever."""
    builder.built = False
    real_serve = admin_app._serve
    calls = []

    async def serve_raising_once(env, slug, mode):
        calls.append(slug)
        if len(calls) == 1:
            raise RuntimeError("control plane went away")
        return await real_serve(env, slug, mode)

    monkeypatch.setattr("app.admin_app._serve", serve_raising_once)
    async with aclient as ac:
        await _alaunch(ac, "qc-run")
        builder.runs[0].finish()
        status = await _status_once_built(ac)
        [failed] = status["failed"]
        assert (failed["slug"], failed["mode"]) == ("qc-run", "edit")
        assert "control plane went away" in failed["error"]

        again = await _alaunch(ac, "qc-run")
        assert again.status_code == 200
        assert again.json() == {"url": "https://nb.example"}


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
        "running": [{"slug": "assets", "mode": "edit", "url": "https://nb.example"}],
        "building": [],
        "failed": [],
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
