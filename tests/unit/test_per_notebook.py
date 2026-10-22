"""Tests for `per_notebook_env`: the declared environment, the dashboard's fields, the pod's env."""

import dataclasses

import flyte
import pytest

from app import config
from app.per_notebook import WORKSPACE_NOTEBOOK_DIR, per_notebook_env
from stargazer.notebooks import (
    NOTEBOOK_RESOURCES,
    notebook_environment,
    notebook_image_base,
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


def test_default_resources_are_the_notebook_resources():
    """With nothing declared the pod gets `NOTEBOOK_RESOURCES`."""
    assert _env().resources == NOTEBOOK_RESOURCES


def test_declared_resources_applied_to_env():
    """A notebook's declared resources are the pod's, as written."""
    resources = flyte.Resources(cpu=2, memory="4Gi", disk="50Gi")
    env = _env(declared=_declared(resources=resources))
    assert env.resources == flyte.Resources(cpu=2, memory="4Gi", disk="50Gi")


def test_resources_a_notebook_leaves_out_keep_their_defaults():
    """Declaring only memory still gets the pod a CPU and its disk."""
    env = _env(declared=_declared(resources=flyte.Resources(memory="16Gi")))
    assert env.resources == dataclasses.replace(NOTEBOOK_RESOURCES, memory="16Gi")


@pytest.mark.parametrize("fields", [None, {"resources": flyte.Resources(cpu=2)}])
def test_a_declaration_without_new_layers_runs_on_the_prebuilt_image(fields):
    """No declaration, or one that only sizes the pod, builds nothing.

    The deployed image is marked prebuilt, so serving hands its URI to Flyte.
    """
    declared = None if fields is None else _declared(**fields)
    assert _env(declared=declared).image == flyte.Image.from_base(config.NOTEBOOK_IMAGE)


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


@pytest.mark.parametrize("fields", [None, {"requires_auth": False}])
def test_pod_sits_behind_union_login(fields):
    """Notebook pods require the platform login, whatever a notebook declares.

    It is the pod's only gate on its public address; the proxy then checks
    ownership.
    """
    declared = None if fields is None else _declared(**fields)
    assert _env(declared=declared).requires_auth is True


def test_declared_env_vars_reach_the_pod_under_the_dashboards():
    """A notebook's env vars are kept; the launcher's own win on a clash."""
    env = _env(
        declared=_declared(env_vars={"QC_MIN_DEPTH": "10", "SG_OWNER_SUBJECT": "1"})
    )
    assert env.env_vars["QC_MIN_DEPTH"] == "10"
    assert env.env_vars["SG_OWNER_SUBJECT"] == SUBJECT


def test_pod_env_carries_the_owner_the_stores_and_the_index(monkeypatch):
    """The pod learns who owns it, where its notebooks and assets are stored and
    which index holds the assets."""
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "s3://bucket/stargazer")
    env = _env()
    assert env.env_vars["SG_OWNER_SUBJECT"] == SUBJECT
    assert env.env_vars["STARGAZER_WORKSPACE_ROOT"] == "s3://bucket/stargazer"
    assert env.env_vars["STARGAZER_ADMIN_URL"] == "http://admin"
    assert env.env_vars["STARGAZER_STORE_ROOT"] == "s3://bucket/stargazer"
    assert (
        env.env_vars["STARGAZER_INDEX_URL"]
        == "dsql://u_x@abc123.dsql.us-west-2.on.aws/assets.u_x?role_arn=arn"
    )


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


def test_pod_gets_the_configured_domain(monkeypatch):
    """Per-notebook pods run in the deploy's domain, not a hardcoded one."""
    monkeypatch.setattr(config, "FLYTE_DOMAIN", "production")
    assert _env().env_vars["FLYTE_DOMAIN"] == "production"


def test_launch_without_a_deployed_image_errors(monkeypatch):
    """With no image baked in, launching says so instead of pulling garbage."""
    monkeypatch.setattr(config, "NOTEBOOK_IMAGE", None)
    with pytest.raises(RuntimeError, match="STARGAZER_NOTEBOOK_IMAGE is unset"):
        _env()
