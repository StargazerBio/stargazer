"""Tests for what a notebook imports from the package root."""

import subprocess
import sys

from conftest import SDK_TYPES

import stargazer
from stargazer.assets.asset import Asset, assemble
from stargazer.bundles import fetch_bundle
from stargazer.config import init_flyte


def test_the_root_exports_what_a_notebook_uses():
    """`from stargazer import ...` reaches the asset base, assembly, bundles and
    Flyte init, as the objects their own modules define."""
    from stargazer import Asset as RootAsset
    from stargazer import assemble as root_assemble
    from stargazer import fetch_bundle as root_fetch_bundle
    from stargazer import init_flyte as root_init_flyte

    assert (RootAsset, root_assemble, root_fetch_bundle, root_init_flyte) == (
        Asset,
        assemble,
        fetch_bundle,
        init_flyte,
    )


def test_the_root_exports_every_asset_type():
    """Every asset type the SDK ships is importable from the root by its name."""
    missing = [
        cls.__name__
        for cls in SDK_TYPES
        if getattr(stargazer, cls.__name__, None) is not cls
    ]

    assert missing == []


def test_importing_the_root_leaves_marimo_unimported():
    """The dashboard imports the package without marimo installed, so the root
    mustn't import it."""
    out = subprocess.run(
        [sys.executable, "-c", "import sys, stargazer; print('marimo' in sys.modules)"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert out.stdout.strip() == "False"
