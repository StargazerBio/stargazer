"""Tests for `devbox/dashboard.py`, the devbox's dashboard deploy.

The script lives outside the shipped packages, so it's loaded from its path.
"""

import sys
from contextlib import contextmanager

import pytest
from conftest import load_devbox_dashboard

from app import config

devbox_dashboard = load_devbox_dashboard()


def test_deploys_the_dashboard_for_a_stand_in_on_the_devbox_store(
    monkeypatch, served_dashboard
):
    """One dashboard in the default project for a stand-in user, on the
    devbox's bucket and Postgres index, with the storage port-forward open
    while it uploads."""
    served_while_open = []

    @contextmanager
    def fake_forward():
        """A port-forward that notes whether the dashboard was served inside it."""
        yield
        served_while_open.append(bool(served_dashboard))

    monkeypatch.setattr(devbox_dashboard, "storage_port_forward", fake_forward)
    assert devbox_dashboard.deploy() == "https://u-jane.apps.example"
    assert served_while_open == [True]
    assert (served_dashboard["ctx"]["project"], served_dashboard["ctx"]["domain"]) == (
        config.FLYTE_PROJECT,
        config.FLYTE_DOMAIN,
    )
    subject, root = devbox_dashboard.SUBJECT, devbox_dashboard.STORE_ROOT
    assert {
        k: served_dashboard["env_vars"][k]
        for k in (
            "SG_STAND_IN_SUBJECT",
            "SG_OWNER_SUBJECT",
            "STARGAZER_OWNER",
            "STARGAZER_WORKSPACE_ROOT",
            "STARGAZER_STORE_ROOT",
            "STARGAZER_INDEX_URL",
        )
    } == {
        "SG_STAND_IN_SUBJECT": subject,
        "SG_OWNER_SUBJECT": subject,
        "STARGAZER_OWNER": subject,
        "STARGAZER_WORKSPACE_ROOT": root,
        "STARGAZER_STORE_ROOT": root,
        "STARGAZER_INDEX_URL": devbox_dashboard.INDEX_URL,
    }


def test_refuses_off_the_devbox(monkeypatch):
    """A stand-in user must never reach a Union deploy."""
    monkeypatch.setattr(config, "TARGET", "union")
    monkeypatch.setattr(
        devbox_dashboard, "init", lambda *a, **k: pytest.fail("init ran")
    )
    monkeypatch.setattr(sys, "argv", ["devbox_dashboard.py"])
    with pytest.raises(SystemExit, match="STARGAZER_TARGET=devbox"):
        devbox_dashboard.main()
