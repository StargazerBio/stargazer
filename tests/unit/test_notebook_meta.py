"""Tests for `app.notebook_meta`: what the dashboard reads from a notebook's setup block.

A notebook declares its tile name, description and pod resources in marimo's
`with app.setup:` block, beside its image. The dashboard reads them with a
parse (no notebook code runs) and rewrites the block from the gear's editor.
"""

import flyte
import pytest

from app.notebook_meta import (
    SetupError,
    notebook_description,
    notebook_name,
    notebook_resources,
    replace_setup_block,
    setup_block_text,
    with_setup_values,
)
from app.notebooks import seed_source

SETUP = (
    "with app.setup:\n"
    "    import flyte\n"
    "\n"
    '    main_name = "QC run"\n'
    '    main_description = "Quality control."\n'
    '    main_resources = flyte.Resources(cpu=4, memory="8Gi")\n'
)

CELL = '@app.cell\ndef _():\n    main_name = "not this"\n    return\n'


def _notebook(setup: str = SETUP) -> str:
    """A marimo notebook source with `setup` (verbatim) and one cell."""
    return (
        "import marimo\n\n"
        'app = marimo.App(width="medium")\n\n'
        f"{setup}\n\n"
        f"{CELL}\n\n"
        'if __name__ == "__main__":\n    app.run()\n'
    )


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def test_reads_name_description_and_resources():
    """The setup block's declarations come back as values."""
    src = _notebook()
    assert notebook_name(src) == "QC run"
    assert notebook_description(src) == "Quality control."
    assert notebook_resources(src) == flyte.Resources(cpu=4, memory="8Gi")


def test_resources_keep_a_request_limit_pair_and_disk():
    """Any literal `flyte.Resources` argument is honored as written."""
    src = _notebook(
        "with app.setup:\n"
        '    main_resources = flyte.Resources(cpu=2, memory=("2Gi", "6Gi"), '
        'disk="50Gi")\n'
    )
    assert notebook_resources(src) == flyte.Resources(
        cpu=2, memory=("2Gi", "6Gi"), disk="50Gi"
    )


def test_undeclared_values_are_empty():
    """A setup block without the declarations has no name, blurb or resources."""
    src = _notebook("with app.setup:\n    import flyte\n")
    assert notebook_name(src) == ""
    assert notebook_description(src) == ""
    assert notebook_resources(src) is None


def test_assignments_inside_a_cell_are_ignored():
    """Only the setup block declares; the cell's `main_name` is not the name."""
    src = _notebook("with app.setup:\n    import flyte\n")
    assert notebook_name(src) == ""


def test_unparseable_source_reads_as_undeclared():
    """A notebook mid-edit with a syntax error still tiles."""
    src = 'with app.setup:\n    main_name = "x"\n    main_resources = (\n'
    assert notebook_name(src) == ""
    assert notebook_resources(src) is None


def test_resources_that_are_not_literal_are_an_error():
    """Resources are read without running code, so they must be literals."""
    src = _notebook("with app.setup:\n    main_resources = flyte.Resources(cpu=CPUS)\n")
    with pytest.raises(SetupError, match="main_resources"):
        notebook_resources(src)


def test_resources_that_are_not_a_resources_call_are_an_error():
    """`main_resources` has to be a `flyte.Resources(...)` call."""
    src = _notebook('with app.setup:\n    main_resources = {"cpu": 2}\n')
    with pytest.raises(SetupError, match=r"flyte\.Resources"):
        notebook_resources(src)


def test_setup_block_text_is_the_whole_block():
    """The editor gets the block from its `with` line to its last line."""
    assert setup_block_text(_notebook()) == SETUP


def test_setup_block_text_keeps_a_trailing_comment():
    """A comment at the end of the block is part of it."""
    setup = SETUP + "    # TODO: more tools\n"
    assert setup_block_text(_notebook(setup)) == setup


def test_setup_block_text_without_a_block_is_none():
    """A notebook with no setup block has nothing to edit."""
    assert setup_block_text("import marimo\napp = marimo.App()\n") is None


# ---------------------------------------------------------------------------
# Rewriting the block
# ---------------------------------------------------------------------------


def test_replace_swaps_only_the_block():
    """The new block lands where the old one was; cells are untouched."""
    new = (
        "with app.setup(hide_code=True):\n"
        "    import flyte\n"
        '    main_resources = flyte.Resources(cpu=8, memory="32Gi")\n'
    )
    src = replace_setup_block(_notebook(), new)
    assert src == _notebook(new)
    assert notebook_resources(src) == flyte.Resources(cpu=8, memory="32Gi")


def test_replace_adds_a_block_to_a_notebook_without_one():
    """The block goes right after `app = marimo.App(...)`, where marimo writes it."""
    src = "import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _():\n    return\n"
    out = replace_setup_block(src, 'with app.setup:\n    main_name = "New"\n')
    assert out == (
        "import marimo\n\napp = marimo.App()\n\n"
        'with app.setup:\n    main_name = "New"\n'
        "\n\n@app.cell\ndef _():\n    return\n"
    )


@pytest.mark.parametrize(
    ("block", "error"),
    [
        ("with app.setup:\n    main_name = (\n", "line 2"),
        ("import os\n", "with app.setup:"),
        ("with app.setup:\n    pass\nimport os\n", "with app.setup:"),
        ("with app.setup:\n    main_resources = flyte.Resources(cpu=n)\n", "literal"),
        ("with app.setup:\n    main_name = 3\n", "main_name"),
    ],
)
def test_replace_refuses_a_block_that_would_break(block, error):
    """A bad edit is refused with the reason, never written."""
    with pytest.raises(SetupError, match=error):
        replace_setup_block(_notebook(), block)


def test_with_setup_values_replaces_a_declared_value():
    """Create and copy set the name over the seed's own."""
    src = with_setup_values(_notebook(), main_name='Say "hi"')
    assert notebook_name(src) == 'Say "hi"'
    assert notebook_description(src) == "Quality control."


def test_with_setup_values_declares_a_missing_value_after_the_imports():
    """A value the block lacks is added after its imports, before the rest."""
    setup = (
        "with app.setup:\n"
        "    import flyte\n"
        "\n"
        "    main_resources = flyte.Resources(cpu=1)\n"
    )
    src = with_setup_values(_notebook(setup), main_name="QC")
    assert setup_block_text(src) == (
        "with app.setup:\n"
        "    import flyte\n"
        '    main_name = "QC"\n'
        "\n"
        "    main_resources = flyte.Resources(cpu=1)\n"
    )


def test_with_setup_values_adds_a_block_when_there_is_none():
    """A notebook without a setup block (a shipped workflow) gets one."""
    src = "import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _():\n    return\n"
    out = with_setup_values(src, main_name="scRNA-seq", main_description="UMAPs.")
    assert notebook_name(out) == "scRNA-seq"
    assert notebook_description(out) == "UMAPs."


@pytest.mark.parametrize("seed", ["blank", "basic"])
def test_seeds_declare_resources_to_edit(seed):
    """New notebooks start with resources in their setup block."""
    assert isinstance(notebook_resources(seed_source(seed)), flyte.Resources)
