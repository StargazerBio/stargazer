"""Tests for where the task images come from: a checkout's source, or a release.

An installed package has no `pyproject.toml` beside its source, so it can't
build its images; it runs its tasks on the images its release published.
"""

import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from stargazer import config

GATK_ENV = Path(config.__file__).parent / "tasks" / "gatk" / "env.py"
VERSION = version("stargazer-bio")


@pytest.fixture
def installed(monkeypatch, tmp_path):
    """`stargazer.config` as it sits in site-packages: no checkout around it."""
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)


def test_an_installed_package_runs_its_tasks_on_its_releases_image(installed):
    """The task image is the published one of the installed version, nothing to build."""
    image = config.task_image(GATK_ENV)

    assert image.uri.endswith(f"/stargazer-gatk:{VERSION}")
    assert image._layers == ()


def test_a_checkout_builds_its_task_image_from_source():
    """A checkout's task image is built (tagged by content), not pulled by version."""
    image = config.task_image(GATK_ENV)

    assert not image.uri.endswith(f":{VERSION}")
    assert image._layers


def test_an_installed_package_runs_its_notebooks_tasks_on_the_released_core_image(
    installed,
):
    """The core image is the published one of the installed version, nothing to build."""
    image = config.core_image("stargazer-template")

    assert image.uri == f"ghcr.io/stargazerbio/stargazer-core:{VERSION}"
    assert image._layers == ()


def test_a_checkout_bundles_hosted_runs_from_its_source():
    """A checkout's runs carry the source tree that holds the `stargazer` package."""
    assert config._bundle_root() == Path(config.__file__).resolve().parents[1]


def test_an_installed_package_bundles_hosted_runs_from_the_notebook(
    installed, monkeypatch, tmp_path
):
    """With the SDK in its image, a run carries only the running notebook's folder."""
    notebook = tmp_path / "workspace" / "analysis.py"
    monkeypatch.setattr(sys.modules["__main__"], "__file__", str(notebook))

    assert config._bundle_root() == tmp_path / "workspace"
