"""Tests for `notebook_base`, the image a notebook's `main_env` builds on."""

from stargazer.notebooks import notebook_image_base

BASE = "registry.example/union/stargazerbio:notebook-app-abc123"


def test_notebook_base_takes_layers_and_keeps_its_base():
    """Layers stack on the deployed notebook image without a clone step."""
    img = notebook_image_base(BASE).with_apt_packages("bcftools")
    assert img.base_image == BASE
    assert img.uri.startswith("notebook-custom:")
