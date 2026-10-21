"""Tests for `per_notebook_env`: resources, auth, and what reaches the pod's env."""

import flyte

from app import config
from app.per_notebook import NOTEBOOK_DISK, WORKSPACE_NOTEBOOK_DIR, per_notebook_env
from stargazer.notebooks import notebook_image_base

SUBJECT = "387300641116005877"


def _env(**overrides):
    """Build a per-notebook env with sensible defaults for the keyword args."""
    kwargs = {
        "slug": "demo",
        "mode": "edit",
        "notebook_path": f"{WORKSPACE_NOTEBOOK_DIR}/demo.py",
        "owner_subject": SUBJECT,
        "admin_url": "http://admin",
        "index_url": "http://dashboard.u-x-development.svc.cluster.local",
    }
    kwargs.update(overrides)
    return per_notebook_env(**kwargs)


def test_default_resources_preserve_legacy_request_limit():
    """With no resources, the env gets one CPU and the ('2Gi','6Gi') memory tuple."""
    env = _env()
    assert env.resources.memory == ("2Gi", "6Gi")
    assert env.resources.cpu == 1


def test_declared_resources_applied_to_env():
    """A notebook's declared resources are the pod's, as written."""
    env = _env(resources=flyte.Resources(cpu=2, memory="4Gi", disk="50Gi"))
    assert env.resources == flyte.Resources(cpu=2, memory="4Gi", disk="50Gi")


def test_resources_a_notebook_leaves_out_keep_their_defaults():
    """Declaring only memory still gets the pod a CPU and its disk."""
    env = _env(resources=flyte.Resources(memory="16Gi"))
    assert env.resources == flyte.Resources(cpu=1, memory="16Gi", disk=NOTEBOOK_DISK)


def test_pod_sits_behind_union_login():
    """Notebook pods require the platform login; the proxy then checks ownership."""
    assert _env().requires_auth is True


def test_pod_env_carries_owner_and_store_root(monkeypatch):
    """The pod learns who owns it and where its notebooks are stored."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "s3://bucket/stargazer")
    env = _env()
    assert env.env_vars["SG_OWNER_SUBJECT"] == SUBJECT
    assert env.env_vars["STARGAZER_WORKSPACE_ROOT"] == "s3://bucket/stargazer"
    assert env.env_vars["STARGAZER_ADMIN_URL"] == "http://admin"


def test_pod_env_carries_the_asset_store_and_index(monkeypatch):
    """Assets go under the workspace root and are indexed through the dashboard."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "s3://bucket/stargazer")
    env = _env()
    assert env.env_vars["STARGAZER_STORE_ROOT"] == "s3://bucket/stargazer"
    assert (
        env.env_vars["STARGAZER_INDEX_URL"]
        == "http://dashboard.u-x-development.svc.cluster.local"
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
    declared = notebook_image_base(config.NOTEBOOK_IMAGE).with_apt_packages("tabix")
    assert _env(image=declared).image == declared


def test_pod_env_names_the_deployed_image_even_on_a_declared_one():
    """The kernel's `notebook_base` is the deployed image, never the declared one."""
    declared = notebook_image_base(config.NOTEBOOK_IMAGE).with_apt_packages("tabix")
    env = _env(image=declared)
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
