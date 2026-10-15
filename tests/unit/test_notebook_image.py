"""Tests for `app.notebook_image`: finding, evaluating and resolving `main_img`.

The evaluation subprocess runs for real. Only the cases that never reach the
image builder are covered here; a real build is verified on Union.
"""

import threading

import pytest

from app import config, notebook_image
from app.notebook_image import (
    ImageResult,
    checked_uri,
    evaluate_main_img,
    extract_main_img,
    launch_image,
    resolve_main_img,
)
from stargazer.notebooks import notebook_image_base

BASE = "test.example/notebook-app:unit"


def _notebook(setup_body: str, cell_body: str = "    return\n") -> str:
    """A marimo notebook source with the given setup and one cell."""
    return (
        "import marimo\n\n"
        'app = marimo.App(width="medium")\n\n'
        f"with app.setup:\n{setup_body}\n\n"
        f"@app.cell\ndef _():\n{cell_body}\n\n"
        'if __name__ == "__main__":\n    app.run()\n'
    )


@pytest.fixture(autouse=True)
def _fresh_builds():
    """Every test starts with no builds in flight."""
    notebook_image._builds.clear()
    yield
    notebook_image._builds.clear()


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


# ---------------------------------------------------------------------------
# evaluate_main_img
# ---------------------------------------------------------------------------


def test_evaluate_gives_the_declared_image():
    """Evaluating the expression gives the same image as writing it out."""
    base = notebook_image_base(BASE)
    img = evaluate_main_img('notebook_base.with_apt_packages("bcftools")', base)
    assert img == base.with_apt_packages("bcftools")


def test_evaluate_refuses_an_image_not_built_on_notebook_base():
    """An image from another base can't boot a notebook pod."""
    with pytest.raises(ValueError, match="notebook_base"):
        evaluate_main_img("flyte.Image.from_debian_base()", notebook_image_base(BASE))


def test_evaluate_refuses_a_non_image():
    """`main_img` has to be a flyte.Image."""
    with pytest.raises(TypeError, match="flyte.Image"):
        evaluate_main_img('"bcftools"', notebook_image_base(BASE))


# ---------------------------------------------------------------------------
# checked_uri
# ---------------------------------------------------------------------------


def test_checked_uri_accepts_a_registry_qualified_uri():
    """A built image's URI names its registry."""
    uri = "791359099513.dkr.ecr.us-west-2.amazonaws.com/union/stargazerbio:nb-abc"
    assert checked_uri(uri) == ImageResult(uri=uri)


def test_checked_uri_refuses_a_bare_name_and_tag():
    """A bare `name:tag` means no builder confirmed the image; it can't be pulled."""
    result = checked_uri("notebook-custom:abc")
    assert result.uri is None
    assert "couldn't be built" in result.error


# ---------------------------------------------------------------------------
# resolve_main_img (real subprocess, no build)
# ---------------------------------------------------------------------------


def test_resolve_bare_notebook_base_is_the_deployed_image():
    """`main_img = notebook_base` adds nothing, so it serves the deployed image."""
    assert resolve_main_img("notebook_base") == ImageResult(uri=config.NOTEBOOK_IMAGE)


def test_resolve_reports_an_undefined_name():
    """The expression can't see other setup-block names; the error says which."""
    result = resolve_main_img("notebook_base.with_apt_packages(*TOOLS)")
    assert result.uri is None
    assert "NameError" in result.error
    assert "TOOLS" in result.error


def test_resolve_reports_a_foreign_base():
    """A wrong base comes back as an error, not a crash."""
    result = resolve_main_img("flyte.Image.from_debian_base()")
    assert result.uri is None
    assert "notebook_base" in result.error


# ---------------------------------------------------------------------------
# launch_image
# ---------------------------------------------------------------------------


@pytest.fixture
def union(monkeypatch):
    """Launches aim at Union, where images can be built."""
    monkeypatch.setattr(config, "TARGET", "union")


@pytest.fixture
def builder(monkeypatch):
    """Replace the subprocess with a build that finishes when told to."""
    calls: list[str] = []
    finish = threading.Event()
    outcome: dict = {"result": ImageResult(uri="reg.example/stargazerbio:nb-1")}

    def fake_resolve(expr):
        calls.append(expr)
        finish.wait(timeout=10)
        return outcome["result"]

    monkeypatch.setattr(notebook_image, "resolve_main_img", fake_resolve)
    monkeypatch.setattr(notebook_image, "BUILD_WAIT_SECONDS", 0.5)
    return calls, finish, outcome


async def test_launch_image_is_none_while_the_build_runs(union, builder):
    """A build still running answers None; asking again joins the same build."""
    calls, finish, _ = builder
    assert await launch_image("notebook_base.with_apt_packages('x')") is None
    assert await launch_image("notebook_base.with_apt_packages('x')") is None
    assert calls == ["notebook_base.with_apt_packages('x')"]
    finish.set()


async def test_launch_image_returns_the_built_uri(union, builder):
    """Once the build finishes, launches get its URI without rebuilding."""
    calls, finish, _ = builder
    finish.set()
    first = await launch_image("e")
    second = await launch_image("e")
    assert first == second == ImageResult(uri="reg.example/stargazerbio:nb-1")
    assert calls == ["e"]


async def test_launch_image_retries_after_a_failed_build(union, builder):
    """A failed build is reported once; the next launch builds again."""
    calls, finish, outcome = builder
    outcome["result"] = ImageResult(error="Image build failed")
    finish.set()
    assert await launch_image("e") == ImageResult(error="Image build failed")
    outcome["result"] = ImageResult(uri="reg.example/stargazerbio:nb-2")
    assert await launch_image("e") == ImageResult(uri="reg.example/stargazerbio:nb-2")
    assert calls == ["e", "e"]


async def test_launch_image_off_union_is_an_error(monkeypatch, builder):
    """The devbox can't build images, so a declared one fails clearly."""
    monkeypatch.setattr(config, "TARGET", "devbox")
    calls, finish, _ = builder
    finish.set()
    result = await launch_image("e")
    assert result.uri is None
    assert "can't build" in result.error
    assert calls == []
