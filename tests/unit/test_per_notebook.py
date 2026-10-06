"""Tests for `per_notebook_env`: resources, auth, and what reaches the pod's env."""

from app import config
from app.notebook_meta import NotebookResources
from app.per_notebook import (
    SNAPSHOT_NOTEBOOK_DIR,
    WORKSPACE_NOTEBOOK_DIR,
    per_notebook_env,
)

SUBJECT = "387300641116005877"


def _env(**overrides):
    """Build a per-notebook env with sensible defaults for the keyword args."""
    kwargs = {
        "slug": "demo",
        "mode": "edit",
        "notebook_path": f"{WORKSPACE_NOTEBOOK_DIR}/demo.py",
        "owner_subject": SUBJECT,
        "admin_url": "http://admin",
    }
    kwargs.update(overrides)
    return per_notebook_env(**kwargs)


def test_default_resources_preserve_legacy_request_limit():
    """With no resources, the env keeps the legacy ('2Gi','6Gi') tuple."""
    env = _env()
    assert env.resources.memory == ("2Gi", "6Gi")
    assert env.resources.cpu is None


def test_custom_resources_applied_to_env():
    """A NotebookResources spec maps onto the env's flyte.Resources."""
    env = _env(resources=NotebookResources(cpu=2, memory="4Gi"))
    assert env.resources.cpu == 2
    assert env.resources.memory == "4Gi"


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


def test_notebook_dirs_are_flat_hydration_targets():
    """Workspace and own snapshots hydrate into fixed, flat pod dirs."""
    assert WORKSPACE_NOTEBOOK_DIR == "/workspace"
    assert SNAPSHOT_NOTEBOOK_DIR == "/snapshots"
