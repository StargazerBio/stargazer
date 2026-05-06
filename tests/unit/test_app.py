"""Tests for the Marimo Flyte App definition."""

import ast
from pathlib import Path


def test_note_env_is_valid_app_environment():
    """note_env is a properly configured AppEnvironment."""
    from flyte.app import AppEnvironment

    from stargazer.config import note_env

    assert isinstance(note_env, AppEnvironment)
    assert note_env.name == "stargazer-notebooks"
    assert note_env.get_port().port == 8080


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
