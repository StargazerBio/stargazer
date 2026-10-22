"""Tests for `app.deploy`: building the notebook image and deploying a dashboard.

Serving is faked at `flyte.with_servecontext`, so nothing reaches a cluster.
"""

import os
import subprocess
from types import SimpleNamespace

import pytest

from app import config, deploy

ALICE = "387300641116005877"


def test_notebook_image_is_the_built_uri(monkeypatch):
    """Dashboards bake in the content-hashed URI the build returns, no retag."""
    monkeypatch.setattr(
        deploy.flyte, "build", lambda img: SimpleNamespace(uri="reg/notebook-app:h1")
    )
    assert deploy.build_notebook_image() == "reg/notebook-app:h1"


def test_dashboard_deploy_keeps_the_env_resolvable(monkeypatch):
    """The served env is built where it's defined, with the owner's settings.

    Flyte resolves `include=` paths and the pod's loader from the frame the
    env was created in; a `clone_with` copy reports `dataclasses.py` instead,
    and the deploy fails on `templates/`.
    """
    served = {}

    def fake_servecontext(**ctx):
        def serve(env):
            served.update(
                ctx=ctx, env=env, env_vars=dict(env.env_vars), domain=env.domain
            )
            return SimpleNamespace(endpoint="https://u-jane.apps.example")

        return SimpleNamespace(serve=serve)

    monkeypatch.setattr(deploy.flyte, "with_servecontext", fake_servecontext)
    monkeypatch.setattr(deploy, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(
        deploy, "get_init_config", lambda: SimpleNamespace(org="stargazerbio")
    )
    assert deploy.deploy_dashboard("u-jane", ALICE) == "https://u-jane.apps.example"
    env = served["env"]
    assert env._caller_frame.filename.endswith("app/admin_app.py")
    assert (served["ctx"]["project"], served["ctx"]["domain"]) == (
        "u-jane",
        "development",
    )
    assert served["domain"].subdomain == "u-jane"
    assert {
        k: served["env_vars"][k]
        for k in (
            "FLYTE_PROJECT",
            "SG_OWNER_SUBJECT",
            "STARGAZER_NOTEBOOK_IMAGE",
            "FLYTE_ORG",
        )
    } == {
        "FLYTE_PROJECT": "u-jane",
        "SG_OWNER_SUBJECT": ALICE,
        "STARGAZER_NOTEBOOK_IMAGE": "reg/notebook-app:h1",
        "FLYTE_ORG": "stargazerbio",
    }


def test_dashboard_deploy_carries_the_asset_store_and_index(monkeypatch):
    """The dashboard owns a local index, stores under the workspace root, and stamps its owner."""
    served = {}

    def fake_servecontext(**ctx):
        def serve(env):
            served.update(env_vars=dict(env.env_vars))
            return SimpleNamespace(endpoint="https://u-jane.apps.example")

        return SimpleNamespace(serve=serve)

    monkeypatch.setattr(config, "WORKSPACE_ROOT", "s3://bucket/stargazer")
    monkeypatch.setenv("STARGAZER_STORE_REGION", "us-west-2")
    monkeypatch.setenv("STARGAZER_ADMIN_SUBJECTS", "391057331988775036")
    monkeypatch.setenv("STARGAZER_PUBLIC_ASSETS", "off")
    monkeypatch.setattr(deploy.flyte, "with_servecontext", fake_servecontext)
    monkeypatch.setattr(deploy, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(deploy, "get_init_config", lambda: SimpleNamespace(org=None))
    deploy.deploy_dashboard("u-jane", ALICE)
    assert served["env_vars"]["STARGAZER_PUBLIC_ASSETS"] == "off"
    assert served["env_vars"]["STARGAZER_STORE_REGION"] == "us-west-2"
    assert served["env_vars"]["STARGAZER_ADMIN_SUBJECTS"] == "391057331988775036"
    assert served["env_vars"]["STARGAZER_STORE_ROOT"] == "s3://bucket/stargazer"
    assert served["env_vars"]["STARGAZER_INDEX_URL"] == "~/.stargazer/index.db"
    assert served["env_vars"]["STARGAZER_OWNER"] == ALICE


def test_dashboard_deploy_bakes_the_release_version(monkeypatch):
    """Each dashboard carries the version it was deployed from, for its page."""
    served = {}

    def fake_servecontext(**ctx):
        def serve(env):
            served.update(env_vars=dict(env.env_vars))
            return SimpleNamespace(endpoint="https://u-jane.apps.example")

        return SimpleNamespace(serve=serve)

    monkeypatch.setattr(deploy.flyte, "with_servecontext", fake_servecontext)
    monkeypatch.setattr(deploy, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(deploy, "get_init_config", lambda: SimpleNamespace(org=None))
    monkeypatch.setattr(deploy, "release_version", lambda: "18fbabe-dirty")
    deploy.deploy_dashboard("u-jane", ALICE)
    assert served["env_vars"]["STARGAZER_VERSION"] == "18fbabe-dirty"


def test_dashboard_deploy_is_versioned_with_the_release(monkeypatch):
    """The deploy's version is the commit it came from, so the console shows it."""
    contexts = []

    def fake_servecontext(**ctx):
        contexts.append(ctx)
        return SimpleNamespace(
            serve=lambda env: SimpleNamespace(endpoint="https://u-jane.apps.example")
        )

    monkeypatch.setattr(deploy.flyte, "with_servecontext", fake_servecontext)
    monkeypatch.setattr(deploy, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(deploy, "get_init_config", lambda: SimpleNamespace(org=None))
    monkeypatch.setattr(deploy, "release_version", lambda: "18fbabe")
    deploy.deploy_dashboard("u-jane", ALICE)
    assert contexts == [
        {"project": "u-jane", "domain": "development", "version": "18fbabe"}
    ]


@pytest.fixture
def bare_git_env(monkeypatch):
    """No inherited `GIT_*` variables: a pre-commit hook's would point at this repo."""
    for name in [n for n in os.environ if n.startswith("GIT_")]:
        monkeypatch.delenv(name)


def test_release_version_is_the_checkout_commit(tmp_path, bare_git_env):
    """The deployer's commit, marked `-dirty` when tracked files have changed."""

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git("init", "-q")
    (tmp_path / "notes.txt").write_text("one")
    git("add", "notes.txt")
    git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-qm", "c")
    sha = git("rev-parse", "--short", "HEAD")
    assert deploy.release_version(tmp_path) == sha
    (tmp_path / "notes.txt").write_text("two")
    assert deploy.release_version(tmp_path) == f"{sha}-dirty"


def test_release_version_outside_a_checkout_is_unknown(tmp_path, bare_git_env):
    """Deploying from something that isn't a git checkout still deploys."""
    assert deploy.release_version(tmp_path) == "unknown"


def test_dashboard_deploy_waits_out_a_stale_watch_failure(monkeypatch):
    """A watch error on a deploy that does come up is not reported as failure.

    Seen on the tenant: the watch tripped on an older failed revision while
    the new one became ready a few seconds later.
    """

    def failing_servecontext(**ctx):
        def serve(env):
            raise RuntimeError("App deployment for app dashboard has failed!")

        return SimpleNamespace(serve=serve)

    states = iter([False, False, True])

    class FakeApp:
        @staticmethod
        def get(name, project, domain):
            active = next(states)
            return SimpleNamespace(
                is_active=lambda: active, endpoint="https://u-jane.apps.example"
            )

    monkeypatch.setattr(deploy.flyte, "with_servecontext", failing_servecontext)
    monkeypatch.setattr(deploy, "App", FakeApp)
    monkeypatch.setattr(deploy, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(deploy.time, "sleep", lambda s: None)
    assert deploy.deploy_dashboard("u-jane", ALICE) == "https://u-jane.apps.example"
