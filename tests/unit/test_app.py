"""Tests for the admin AppEnvironment and deploy entrypoint."""


def test_app_env_is_valid_app_environment():
    """app_env is a properly configured AppEnvironment."""
    from flyte.app import AppEnvironment

    from app.admin_app import app_env

    assert isinstance(app_env, AppEnvironment)
    assert app_env.name == "admin-app"
    assert app_env.get_port().port == 8080


def test_main_function_exists():
    """admin_app exposes a main() entry point."""
    from app.admin_app import main

    assert callable(main)
