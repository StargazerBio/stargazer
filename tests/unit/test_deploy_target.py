"""Tests for the devbox/union deploy-target switch (`STARGAZER_TARGET`).

Import-time defaults are checked in a fresh interpreter, since both config
modules resolve the environment once at import.
"""

import base64
import os
import subprocess
import sys

import pytest


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


def test_devbox_defaults_to_a_local_registry():
    """The devbox (default target) pushes to a registry of its own."""
    assert _fresh(_REGISTRY) != "None"


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


_SECRETS = (
    "from stargazer.config import STARGAZER_SECRETS as s; "
    "print(sorted((x.key, x.as_env_var) for x in s))"
)


def test_union_pods_call_union_as_their_project():
    """Every pod on Union gets its project's key where flyte's in-cluster client reads it."""
    assert "('UNION_API_KEY', '_UNION_EAGER_API_KEY')" in _fresh(
        _SECRETS, STARGAZER_TARGET="union"
    )


def test_devbox_pods_get_no_union_key():
    """The devbox has no key to give, and a declared secret it lacks stops the pod."""
    assert "UNION_API_KEY" not in _fresh(_SECRETS)


_APP = "from app import config as c; print(c.TARGET, c.FLYTE_CONFIG.name)"


def test_app_config_per_target():
    """Each target picks its own Flyte config file."""
    assert _fresh(_APP) == "devbox config.yaml"
    assert _fresh(_APP, STARGAZER_TARGET="union") == "union union.yaml"


# An API key in Flyte's format (base64 of endpoint:client-id:secret:org), for
# a tenant that's never contacted: init only records it.
_FAKE_API_KEY = base64.b64encode(b"tenant.example.com:ci:secret:org").decode()
_INIT = (
    "from app.init import init; from flyte._initialize import get_init_config; "
    "init(); c = get_init_config(); print(c.image_builder, c.project)"
)


def test_api_key_deployer_builds_in_the_default_project_remotely():
    """A deployer with only an API key builds Union's images remotely, in flytesnacks.

    The key carries no config file, which is where the deployer's builder and
    project otherwise come from.
    """
    assert (
        _fresh(_INIT, STARGAZER_TARGET="union", FLYTE_API_KEY=_FAKE_API_KEY)
        == "remote flytesnacks"
    )
