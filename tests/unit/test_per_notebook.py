"""Tests for `per_notebook_env`: the declared environment, the dashboard's fields, the pod's env."""

import flyte

from app import config
from app.per_notebook import WORKSPACE_NOTEBOOK_DIR, per_notebook_env
from stargazer.notebooks import NOTEBOOK_DISK, notebook_environment, notebook_image_base

SUBJECT = "387300641116005877"


def _env(**overrides):
    """Build a per-notebook env with sensible defaults for the keyword args."""
    kwargs = {
        "slug": "demo",
        "mode": "edit",
        "notebook_path": f"{WORKSPACE_NOTEBOOK_DIR}/demo.py",
        "owner_subject": SUBJECT,
        "admin_url": "http://admin",
        "index_url": "dsql://u_x@abc123.dsql.us-west-2.on.aws/assets.u_x?role_arn=arn",
    }
    kwargs.update(overrides)
    return per_notebook_env(**kwargs)


def _declared(**fields):
    """A notebook's `main_env`: a clone of `notebook_env` on the deployed image."""
    base = notebook_image_base(config.NOTEBOOK_IMAGE)
    return notebook_environment(base).clone_with(name="my-analysis", **fields)


def _layered():
    """The deployed image with one more tool on it."""
    return notebook_image_base(config.NOTEBOOK_IMAGE).with_apt_packages("tabix")


def test_default_resources_preserve_legacy_request_limit():
    """With no resources, the env gets one CPU and the ('2Gi','6Gi') memory tuple."""
    env = _env()
    assert env.resources.memory == ("2Gi", "6Gi")
    assert env.resources.cpu == 1


def test_without_a_declaration_the_pod_runs_on_the_prebuilt_image():
    """The deployed image is marked prebuilt, so serving builds nothing."""
    assert _env().image == flyte.Image.from_base(config.NOTEBOOK_IMAGE)


def test_declared_resources_applied_to_env():
    """A notebook's declared resources are the pod's, as written."""
    resources = flyte.Resources(cpu=2, memory="4Gi", disk="50Gi")
    env = _env(declared=_declared(resources=resources))
    assert env.resources == flyte.Resources(cpu=2, memory="4Gi", disk="50Gi")


def test_resources_a_notebook_leaves_out_keep_their_defaults():
    """Declaring only memory still gets the pod a CPU and its disk."""
    env = _env(declared=_declared(resources=flyte.Resources(memory="16Gi")))
    assert env.resources == flyte.Resources(cpu=1, memory="16Gi", disk=NOTEBOOK_DISK)


def test_a_declaration_without_new_layers_runs_on_the_prebuilt_image():
    """Sizing the pod alone builds nothing."""
    env = _env(declared=_declared(resources=flyte.Resources(cpu=2)))
    assert env.image == flyte.Image.from_base(config.NOTEBOOK_IMAGE)


def test_the_dashboard_names_and_starts_the_pod():
    """The app's name, command and port are the dashboard's, whatever's declared."""
    env = _env(declared=_declared(args=["sleep", "infinity"], port=9000))
    assert env.name == "nb-demo-edit"
    assert env.args == [
        "exec",
        "/usr/local/bin/launch-notebook.sh",
        "edit",
        f"{WORKSPACE_NOTEBOOK_DIR}/demo.py",
    ]
    assert env.port.port == 8080


def test_pod_sits_behind_union_login():
    """Notebook pods require the platform login; the proxy then checks ownership."""
    assert _env().requires_auth is True


def test_a_declaration_cannot_turn_the_login_off():
    """The platform login is the pod's only gate on its public address."""
    assert _env(declared=_declared(requires_auth=False)).requires_auth is True


def test_declared_env_vars_reach_the_pod_under_the_dashboards():
    """A notebook's env vars are kept; the launcher's own win on a clash."""
    env = _env(
        declared=_declared(env_vars={"QC_MIN_DEPTH": "10", "SG_OWNER_SUBJECT": "1"})
    )
    assert env.env_vars["QC_MIN_DEPTH"] == "10"
    assert env.env_vars["SG_OWNER_SUBJECT"] == SUBJECT


def test_pod_knows_which_notebook_it_serves():
    """The proxy turns away sessions for any other notebook."""
    assert _env().env_vars["SG_NOTEBOOK_PATH"] == f"{WORKSPACE_NOTEBOOK_DIR}/demo.py"


def test_pod_env_carries_owner_and_store_root(monkeypatch):
    """The pod learns who owns it and where its notebooks are stored."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "s3://bucket/stargazer")
    env = _env()
    assert env.env_vars["SG_OWNER_SUBJECT"] == SUBJECT
    assert env.env_vars["STARGAZER_WORKSPACE_ROOT"] == "s3://bucket/stargazer"
    assert env.env_vars["STARGAZER_ADMIN_URL"] == "http://admin"


def test_pod_env_carries_the_asset_store_and_index(monkeypatch):
    """Assets go under the workspace root and are indexed in the owner's table."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "s3://bucket/stargazer")
    env = _env()
    assert env.env_vars["STARGAZER_STORE_ROOT"] == "s3://bucket/stargazer"
    assert (
        env.env_vars["STARGAZER_INDEX_URL"]
        == "dsql://u_x@abc123.dsql.us-west-2.on.aws/assets.u_x?role_arn=arn"
    )


def test_pod_env_has_no_git_or_session_credentials():
    """Nothing from the old fork/session model reaches the pod."""
    env = _env()
    for gone in (
        "FORK_FULL_NAME",
        "FORK_OWNER",
        "SG_POD_TOKEN",
        "SG_POD_KEY",
        "SESSION_SECRET",
        "STARGAZER_SECURE_COOKIES",
        "GITHUB_TOKEN",
    ):
        assert gone not in env.env_vars


def test_pod_runs_the_image_a_notebook_declares():
    """A declared image becomes the app's image, for serve to build."""
    assert _env(declared=_declared(image=_layered())).image == _layered()


def test_pod_env_names_the_deployed_image_even_on_a_declared_one():
    """The kernel's `notebook_base` is the deployed image, never the declared one."""
    env = _env(declared=_declared(image=_layered()))
    assert env.env_vars["STARGAZER_NOTEBOOK_IMAGE"] == "test.example/notebook-app:unit"


def test_pod_gets_the_pinata_key_as_a_secret():
    """The org's Pinata key reaches the pod as a secret, never in the spec's env."""
    env = _env()
    assert env.secrets == [flyte.Secret(key="PINATA_JWT", as_env_var="PINATA_JWT")]
    assert "PINATA_JWT" not in env.env_vars


def test_pod_env_carries_the_token_check(monkeypatch):
    """The proxy checks tokens against the same issuer, for the same people."""
    monkeypatch.setattr(config, "AUTH_ISSUER", "https://signin.example.test")
    monkeypatch.setattr(config, "ADMIN_SUBJECTS", frozenset({"2", "1"}))
    env = _env()
    assert env.env_vars["SG_AUTH_ISSUER"] == "https://signin.example.test"
    assert env.env_vars["SG_ADMIN_SUBJECTS"] == "1,2"
