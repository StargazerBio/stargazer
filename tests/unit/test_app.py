"""Tests for the Marimo Flyte App definition."""

import ast
from pathlib import Path


def test_marimo_env_is_valid_app_environment():
    """marimo_env is a properly configured AppEnvironment."""
    from stargazer.app import marimo_env

    from flyte.app import AppEnvironment

    assert isinstance(marimo_env, AppEnvironment)
    assert marimo_env.name == "stargazer-notebooks"
    assert marimo_env.get_port().port == 8080


def test_main_function_exists():
    """app module exposes a main() entry point."""
    from stargazer.app import main

    assert callable(main)


def test_getting_started_notebook_is_valid_python():
    """Starter notebook compiles without syntax errors."""
    notebook_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "stargazer"
        / "notebooks"
        / "getting_started.py"
    )
    assert notebook_path.exists(), f"Notebook not found: {notebook_path}"
    source = notebook_path.read_text()
    ast.parse(source)
