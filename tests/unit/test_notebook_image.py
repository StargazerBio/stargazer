"""Tests for `app.notebook_image`: finding a notebook's `main_img` and evaluating it."""

import pytest

from app import config
from app.notebook_image import MainImgError, evaluate_main_img, extract_main_img
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


@pytest.fixture
def union(monkeypatch):
    """Launches aim at Union, where images can be built."""
    monkeypatch.setattr(config, "TARGET", "union")


# ---------------------------------------------------------------------------
# extract_main_img
# ---------------------------------------------------------------------------


def test_extract_reads_the_setup_assignment():
    """`main_img` in the setup block comes back as its expression."""
    src = _notebook(
        "    from stargazer.notebooks import notebook_base\n"
        "    main_img = notebook_base.with_apt_packages(\n"
        '        "bcftools"\n'
        "    )\n"
    )
    assert extract_main_img(src) == "notebook_base.with_apt_packages('bcftools')"


def test_extract_reads_a_setup_block_with_options():
    """`with app.setup(hide_code=True):` is the same block."""
    src = _notebook("    main_img = notebook_base\n").replace(
        "with app.setup:", "with app.setup(hide_code=True):"
    )
    assert extract_main_img(src) == "notebook_base"


def test_extract_without_main_img_is_none():
    """A setup block that declares no image means the default image."""
    assert extract_main_img(_notebook("    import marimo as mo\n")) is None


def test_extract_ignores_main_img_inside_a_cell():
    """Only the setup block declares the pod image; cells are ignored."""
    src = _notebook(
        "    import marimo as mo\n",
        cell_body="    main_img = notebook_base\n    return\n",
    )
    assert extract_main_img(src) is None


def test_extract_of_unparseable_source_is_none():
    """A notebook mid-edit with a syntax error launches on the default image."""
    assert extract_main_img("with app.setup:\n    main_img = (\n") is None


def test_template_declares_an_image_on_notebook_base(union):
    """Notebooks created from the template start with a working `main_img`."""
    expr = extract_main_img(seed_source("template"))
    assert expr == "notebook_base.with_apt_packages('bcftools')"
    assert evaluate_main_img(expr).base_image == config.NOTEBOOK_IMAGE


# ---------------------------------------------------------------------------
# evaluate_main_img
# ---------------------------------------------------------------------------


def test_evaluate_builds_on_the_deployed_notebook_image(union):
    """The expression's `notebook_base` is this dashboard's notebook image."""
    img = evaluate_main_img('notebook_base.with_apt_packages("bcftools")')
    assert img == notebook_image_base(config.NOTEBOOK_IMAGE).with_apt_packages(
        "bcftools"
    )


def test_evaluate_reports_an_undefined_name(union):
    """The expression can't see other setup-block names; the error says which."""
    with pytest.raises(MainImgError, match=r"NameError.*TOOLS"):
        evaluate_main_img("notebook_base.with_apt_packages(*TOOLS)")


def test_evaluate_refuses_an_image_not_built_on_notebook_base(union):
    """An image from another base can't boot a notebook pod."""
    with pytest.raises(MainImgError, match="built on notebook_base"):
        evaluate_main_img("flyte.Image.from_debian_base()")


def test_evaluate_refuses_a_non_image(union):
    """`main_img` has to be a flyte.Image."""
    with pytest.raises(MainImgError, match="flyte.Image"):
        evaluate_main_img('"bcftools"')


def test_evaluate_off_union_is_an_error(monkeypatch):
    """The devbox can't build images, so a declared one fails clearly."""
    monkeypatch.setattr(config, "TARGET", "devbox")
    with pytest.raises(MainImgError, match="can't build"):
        evaluate_main_img("notebook_base")
