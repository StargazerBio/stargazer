"""Unit-test fixtures for the app tier."""

import pytest

from app import config


@pytest.fixture(autouse=True)
def deployed_notebook_image(monkeypatch):
    """Stand in for the notebook image URI a real deploy bakes into the admin pod."""
    monkeypatch.setattr(config, "NOTEBOOK_IMAGE", "test.example/notebook-app:unit")
