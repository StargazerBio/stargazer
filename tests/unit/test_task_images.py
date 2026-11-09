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


TEMPLATE = Path(config.__file__).parent / "notebooks" / "templates" / "basic.py"


def _pixi_manifest(image) -> str:
    """The pixi manifest `image`'s header layer installs."""
    return next(
        layer.render_manifest() for layer in image._layers if hasattr(layer, "script")
    )


def _above_header(image) -> list:
    """`image`'s layers after its header's, the ones its base doesn't bring."""
    layers = list(image._layers)
    return layers[[hasattr(layer, "script") for layer in layers].index(True) + 1 :]


def test_a_notebook_image_builds_from_its_header_without_the_pods_sdk_path():
    """The header's packages install, its SDK from PyPI; the pod-only path is gone."""
    manifest = _pixi_manifest(config.notebook_image(TEMPLATE, "stargazer-template"))

    assert 'bcftools = "1.*"' in manifest
    assert 'stargazer-bio = "*"' in manifest
    assert "/stargazer" not in manifest


def test_a_checkout_notebook_image_installs_the_checkout_on_top():
    """From a checkout, the source goes on top of the header's released SDK."""
    image = config.notebook_image(TEMPLATE, "stargazer-template")

    commands = [
        c for layer in _above_header(image) for c in getattr(layer, "commands", ())
    ]
    assert commands == ["uv pip install --no-cache /opt/stargazer"]


def test_an_installed_notebook_image_installs_the_kernels_version(installed):
    """Installed, the release of the kernel's version goes on top instead."""
    image = config.notebook_image(TEMPLATE, "stargazer-template")

    packages = [
        p for layer in _above_header(image) for p in getattr(layer, "packages", ())
    ]
    assert packages == [f"stargazer-bio=={VERSION}"]


def test_a_notebook_image_is_the_same_wherever_its_header_is_copied(
    monkeypatch, tmp_path
):
    """The kernel and a cluster pod each copy the header, and name the same image."""
    monkeypatch.setenv("STARGAZER_LOCAL", str(tmp_path / "kernel"))
    kernel = config.notebook_image(TEMPLATE, "stargazer-template").uri
    monkeypatch.setenv("STARGAZER_LOCAL", str(tmp_path / "pod"))

    assert config.notebook_image(TEMPLATE, "stargazer-template").uri == kernel


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
