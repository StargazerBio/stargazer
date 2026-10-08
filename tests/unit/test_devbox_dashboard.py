"""Tests for `cli/devbox_dashboard.py`, the devbox's dashboard deploy.

The script lives outside the shipped packages, so it's loaded from its path.
"""

import importlib.util
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app import config, onboard
from stargazer.config import PROJECT_ROOT

_spec = importlib.util.spec_from_file_location(
    "devbox_dashboard", PROJECT_ROOT / "cli" / "devbox_dashboard.py"
)
devbox_dashboard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(devbox_dashboard)


def test_deploys_the_dashboard_for_a_stand_in_on_the_devbox_store(monkeypatch):
    """One dashboard in the default project for a stand-in user, on the
    devbox's bucket, with the storage port-forward open while it uploads."""
    served, steps = {}, []

    def fake_servecontext(**ctx):
        def serve(env):
            served.update(ctx=ctx, env_vars=dict(env.env_vars))
            steps.append("served")
            return SimpleNamespace(endpoint="http://dashboard.devbox.example:30081")

        return SimpleNamespace(serve=serve)

    @contextmanager
    def fake_forward():
        steps.append("open")
        yield
        steps.append("closed")

    monkeypatch.setattr(onboard.flyte, "with_servecontext", fake_servecontext)
    monkeypatch.setattr(onboard, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(onboard, "get_init_config", lambda: SimpleNamespace(org=None))
    monkeypatch.setattr(devbox_dashboard, "storage_port_forward", fake_forward)
    assert devbox_dashboard.deploy() == "http://dashboard.devbox.example:30081"
    assert steps == ["open", "served", "closed"]
    assert served["ctx"] == {"project": "flytesnacks", "domain": "development"}
    assert {
        k: served["env_vars"][k]
        for k in (
            "SG_STAND_IN_SUBJECT",
            "SG_OWNER_SUBJECT",
            "STARGAZER_OWNER",
            "STARGAZER_WORKSPACE_ROOT",
            "STARGAZER_STORE_ROOT",
        )
    } == {
        "SG_STAND_IN_SUBJECT": "devbox-user",
        "SG_OWNER_SUBJECT": "devbox-user",
        "STARGAZER_OWNER": "devbox-user",
        "STARGAZER_WORKSPACE_ROOT": "s3://flyte-data/stargazer",
        "STARGAZER_STORE_ROOT": "s3://flyte-data/stargazer",
    }


def test_refuses_off_the_devbox(monkeypatch):
    """A stand-in user must never reach a Union deploy."""
    monkeypatch.setattr(config, "TARGET", "union")
    monkeypatch.setattr(devbox_dashboard, "init", lambda *a, **k: pytest.fail("init ran"))
    monkeypatch.setattr(sys, "argv", ["devbox_dashboard.py"])
    with pytest.raises(SystemExit, match="STARGAZER_TARGET=devbox"):
        devbox_dashboard.main()
