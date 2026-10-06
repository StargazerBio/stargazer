"""Tests for the devbox/union deploy-target switch (`STARGAZER_TARGET`).

Import-time defaults are checked in a fresh interpreter, since both config
modules resolve the environment once at import.
"""

import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app import admin_app, config
from app.per_notebook import per_notebook_env


def _nb_env():
    """A per-notebook env with placeholder launch arguments."""
    return per_notebook_env(
        slug="demo",
        mode="edit",
        notebook_path="/workspace/x.py",
        owner_subject="387300641116005877",
        admin_url="http://admin",
    )


def _fresh(code: str, **env: str) -> str:
    """Run `code` in a clean interpreter with `env` overlaid; return stdout."""
    base = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("STARGAZER_", "FLYTE_DOMAIN"))
    }
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**base, **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


_REGISTRY = "import os, stargazer.config; print(os.environ.get('STARGAZER_REGISTRY'))"


def test_devbox_defaults_to_local_registry():
    """The devbox (default target) pushes to the in-cluster registry."""
    assert _fresh(_REGISTRY) == "localhost:30000"


def test_union_leaves_registry_to_the_builder():
    """On union no registry is set, so the remote builder uses Union's own."""
    assert _fresh(_REGISTRY, STARGAZER_TARGET="union") == "None"


def test_explicit_registry_wins_on_any_target():
    """An exported STARGAZER_REGISTRY is honored as-is."""
    assert (
        _fresh(_REGISTRY, STARGAZER_TARGET="union", STARGAZER_REGISTRY="r.io/x")
        == "r.io/x"
    )


def test_unknown_target_fails_loudly():
    """A typo'd target errors at import instead of silently meaning devbox."""
    with pytest.raises(subprocess.CalledProcessError):
        _fresh("import stargazer.config", STARGAZER_TARGET="prod")


def test_target_is_forwarded_into_pods():
    """Admin, notebook and task pods resolve images the same way as the deployer."""
    code = "from stargazer.config import STARGAZER_ENV_VARS as e; print(e['STARGAZER_TARGET'])"
    assert _fresh(code, STARGAZER_TARGET="union") == "union"


_APP = "from app import config as c; print(c.TARGET, c.FLYTE_CONFIG.name)"


def test_app_config_per_target():
    """Each target picks its own Flyte config file."""
    assert _fresh(_APP) == "devbox config.yaml"
    assert _fresh(_APP, STARGAZER_TARGET="union") == "union union.yaml"


def test_notebook_pod_gets_configured_domain(monkeypatch):
    """Per-notebook pods run in the deploy's domain, not a hardcoded one."""
    monkeypatch.setattr(config, "FLYTE_DOMAIN", "production")
    assert _nb_env().env_vars["FLYTE_DOMAIN"] == "production"


def test_notebook_pod_uses_the_deployed_image(monkeypatch):
    """Notebook pods run the exact image built at deploy, not a mutable tag."""
    monkeypatch.setattr(
        config, "NOTEBOOK_IMAGE", "registry.example/notebook-app:abc123"
    )
    assert _nb_env().image.uri == "registry.example/notebook-app:abc123"


def test_notebook_launch_without_deployed_image_errors(monkeypatch):
    """With no image baked in, launching says so instead of pulling garbage."""
    monkeypatch.setattr(config, "NOTEBOOK_IMAGE", None)
    with pytest.raises(RuntimeError, match="STARGAZER_NOTEBOOK_IMAGE"):
        _nb_env()


def test_storage_port_forward_is_devbox_only(monkeypatch):
    """Off the devbox, deploy never touches kubectl (it may point anywhere)."""
    calls = []
    monkeypatch.setattr(config, "TARGET", "union")
    monkeypatch.setattr(admin_app.subprocess, "Popen", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(admin_app, "_port_open", lambda *a: False)
    admin_app._start_storage_port_forward()
    assert calls == []


def test_build_notebook_image_returns_built_uri(monkeypatch):
    """The deploy uses the built URI directly; no docker retag step."""
    monkeypatch.setattr(
        admin_app.flyte, "build", lambda img: SimpleNamespace(uri="reg/notebook-app:h1")
    )
    monkeypatch.setattr(
        admin_app.subprocess, "run", lambda *a, **k: pytest.fail("no docker retag")
    )
    assert admin_app._build_notebook_image() == "reg/notebook-app:h1"
