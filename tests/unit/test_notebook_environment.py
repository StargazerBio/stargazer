"""Tests for `app.notebook_environment`: finding a notebook's `main_env` and evaluating it."""

import flyte
import flyte.app
import pytest
from flyte._environment import list_loaded_environments

from app import config
from app.notebook_environment import (
    MainEnvError,
    evaluate_main_env,
    extract_main_env,
    forget_new_environments,
)
from app.notebooks import seed_source
from stargazer.notebooks import notebook_image_base


def _notebook(setup_body: str, cell_body: str = "    return\n") -> str:
    """A marimo notebook source with the given setup and one cell."""
    return (
        "import marimo\n\n"
        'app = marimo.App(width="medium")\n\n'
        f"with app.setup:\n{setup_body}\n\n"
        f"@app.cell\ndef _():\n{cell_body}\n\n"
        'if __name__ == "__main__":\n    app.run()\n'
    )


# ---------------------------------------------------------------------------
# extract_main_env
# ---------------------------------------------------------------------------


def test_extract_reads_the_setup_assignment():
    """`main_env` in the setup block comes back as its expression."""
    src = _notebook(
        "    from stargazer.notebooks import notebook_env\n"
        "    main_env = notebook_env.clone_with(\n"
        '        name="qc"\n'
        "    )\n"
    )
    assert extract_main_env(src) == "notebook_env.clone_with(name='qc')"


def test_extract_reads_a_setup_block_with_options():
    """`with app.setup(hide_code=True):` is the same block."""
    src = _notebook("    main_env = notebook_env\n").replace(
        "with app.setup:", "with app.setup(hide_code=True):"
    )
    assert extract_main_env(src) == "notebook_env"


def test_extract_without_main_env_is_none():
    """A setup block that declares no environment means the default one."""
    assert extract_main_env(_notebook("    import marimo as mo\n")) is None


def test_extract_ignores_main_env_inside_a_cell():
    """Only the setup block declares the pod's environment; cells are ignored."""
    src = _notebook(
        "    import marimo as mo\n",
        cell_body="    main_env = notebook_env\n    return\n",
    )
    assert extract_main_env(src) is None


def test_extract_of_unparseable_source_is_none():
    """A notebook mid-edit with a syntax error launches on the default environment."""
    assert extract_main_env("with app.setup:\n    main_env = (\n") is None


def test_basic_template_declares_an_environment_on_notebook_base(union):
    """Notebooks created from the basic template start with a working `main_env`."""
    env = evaluate_main_env(extract_main_env(seed_source("basic")))
    assert env.image == notebook_image_base(config.NOTEBOOK_IMAGE).with_apt_packages(
        "bcftools"
    )


def test_blank_template_declares_an_environment_the_devbox_can_launch(devbox):
    """The blank template sizes its pod without an image to build."""
    env = evaluate_main_env(extract_main_env(seed_source("blank")))
    assert env.image == notebook_image_base(config.NOTEBOOK_IMAGE)


# ---------------------------------------------------------------------------
# evaluate_main_env
# ---------------------------------------------------------------------------


def test_evaluate_builds_on_the_deployed_notebook_image(union):
    """The expression's `notebook_env` and `notebook_base` are this dashboard's."""
    env = evaluate_main_env(
        "notebook_env.clone_with(name='qc', "
        "image=notebook_base.with_apt_packages('bcftools'), "
        "resources=flyte.Resources(cpu=2, memory='4Gi'))"
    )
    assert isinstance(env, flyte.app.AppEnvironment)
    assert env.image == notebook_image_base(config.NOTEBOOK_IMAGE).with_apt_packages(
        "bcftools"
    )
    assert env.resources == flyte.Resources(cpu=2, memory="4Gi")


def test_evaluate_reports_an_undefined_name(union):
    """The expression can't see other setup-block names; the error says which."""
    with pytest.raises(MainEnvError, match=r"NameError.*TOOLS"):
        evaluate_main_env("notebook_env.clone_with(name='qc', image=TOOLS)")


def test_evaluate_refuses_an_image_not_built_on_notebook_base(union):
    """An image from another base can't boot a notebook pod."""
    with pytest.raises(MainEnvError, match="built on notebook_base"):
        evaluate_main_env(
            "notebook_env.clone_with(name='qc', image=flyte.Image.from_debian_base())"
        )


def test_evaluate_refuses_a_non_environment(union):
    """`main_env` has to be an AppEnvironment, not just its image."""
    with pytest.raises(MainEnvError, match="AppEnvironment"):
        evaluate_main_env("notebook_base.with_apt_packages('bcftools')")


def test_evaluate_off_union_refuses_an_image_to_build(devbox):
    """The devbox can't build images, so a declared one fails clearly."""
    with pytest.raises(MainEnvError, match="can't build"):
        evaluate_main_env(
            "notebook_env.clone_with(name='qc', "
            "image=notebook_base.with_apt_packages('bcftools'))"
        )


def test_evaluate_off_union_takes_resources(devbox):
    """Sizing the pod needs no build, so the devbox serves it."""
    env = evaluate_main_env(
        "notebook_env.clone_with(name='qc', resources=flyte.Resources(cpu=2))"
    )
    assert env.resources == flyte.Resources(cpu=2)


# ---------------------------------------------------------------------------
# forget_new_environments
# ---------------------------------------------------------------------------


def test_evaluating_leaves_the_registry_as_it_was(union):
    """Environments built while evaluating don't stay registered in the dashboard."""
    before = [id(env) for env in list_loaded_environments()]
    with forget_new_environments():
        evaluate_main_env("notebook_env.clone_with(name='qc').clone_with(name='qc-2')")
    assert [id(env) for env in list_loaded_environments()] == before
