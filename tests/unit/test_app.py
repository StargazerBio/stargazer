"""Tests for the Marimo Flyte App definition."""


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
