"""Tests for which image the task environments run: built in a checkout, published outside one."""

import tomllib

import flyte

from stargazer.config import PROJECT_ROOT, gatk_env, scrna_env, task_image


def _no_build(name: str) -> flyte.Image:
    """A recipe that must not be used."""
    raise AssertionError(f"built {name} outside a checkout")


def test_installed_package_uses_the_published_image_for_its_version(tmp_path):
    """Without a project at the root, an environment runs the image published for the installed version."""
    version = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())["project"][
        "version"
    ]

    image = task_image("stargazer-gatk", _no_build, root=tmp_path)

    assert image.uri == f"ghcr.io/stargazerbio/stargazer-gatk:{version}"


def test_checkout_builds_its_own_image():
    """In a checkout an environment builds its recipe."""
    built = flyte.Image.from_debian_base(name="stargazer-test")

    assert task_image("stargazer-test", lambda name: built, root=PROJECT_ROOT) is built


def test_this_checkout_builds_both_task_images():
    """The gatk and scrna environments build their own images here, not pull published ones."""
    for env, name in ((gatk_env, "stargazer-gatk"), (scrna_env, "stargazer-scrna")):
        assert env.image.name == name
        assert not env.image.uri.startswith("ghcr.io/stargazerbio/")
