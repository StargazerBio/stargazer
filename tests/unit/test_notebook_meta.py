"""Tests for `app.notebook_meta`: what the dashboard reads from a notebook's setup block.

A notebook declares its tile name and description in marimo's
`with app.setup:` block, beside its pod's environment. The dashboard reads them
with a parse (no notebook code runs) and rewrites the block from the gear's
editor.
"""

import pytest

from app.notebook_meta import (
    SetupError,
    notebook_description,
    notebook_name,
    replace_setup_body,
    setup_body,
    with_setup_values,
)

BODY = (
    "import flyte\n"
    "\n"
    'main_name = "QC run"\n'
    'main_description = "Quality control."\n'
    'main_env = notebook_env.clone_with(name="qc", resources=flyte.Resources(cpu=4))\n'
)

SETUP = "with app.setup:\n" + "".join(
    f"    {line}" if line.strip() else line for line in BODY.splitlines(keepends=True)
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


def test_reads_name_and_description():
    """The setup block's declarations come back as values."""
    src = _notebook()
    assert notebook_name(src) == "QC run"
    assert notebook_description(src) == "Quality control."


def test_undeclared_values_are_empty():
    """A setup block without the declarations has no name or blurb."""
    src = _notebook("with app.setup:\n    import flyte\n")
    assert notebook_name(src) == ""
    assert notebook_description(src) == ""


def test_assignments_inside_a_cell_are_ignored():
    """Only the setup block declares; the cell's `main_name` is not the name."""
    src = _notebook("with app.setup:\n    import flyte\n")
    assert notebook_name(src) == ""


def test_unparseable_source_reads_as_undeclared():
    """A notebook mid-edit with a syntax error still tiles."""
    src = 'with app.setup:\n    main_name = "x"\n    main_env = (\n'
    assert notebook_name(src) == ""


def test_setup_body_is_the_block_without_its_header_and_indent():
    """The editor gets the block's body, flush left."""
    assert setup_body(_notebook()) == BODY


def test_setup_body_keeps_a_trailing_comment():
    """A comment at the end of the block is part of it."""
    setup = SETUP + "    # TODO: more tools\n"
    assert setup_body(_notebook(setup)) == BODY + "# TODO: more tools\n"


def test_setup_body_without_a_block_is_none():
    """A notebook with no setup block has nothing to edit."""
    assert setup_body("import marimo\napp = marimo.App()\n") is None


# ---------------------------------------------------------------------------
# Rewriting the block
# ---------------------------------------------------------------------------


def test_replace_swaps_only_the_body():
    """The new body lands under the block's own header; cells are untouched."""
    src = _notebook(SETUP.replace("with app.setup:", "with app.setup(hide_code=True):"))
    out = replace_setup_body(src, 'import flyte\nmain_name = "Bigger"\n')
    assert out == _notebook(
        'with app.setup(hide_code=True):\n    import flyte\n    main_name = "Bigger"\n'
    )


def test_replace_round_trips_the_body():
    """Saving the body the editor showed changes nothing."""
    src = _notebook(SETUP + "    # TODO: more tools\n")
    assert replace_setup_body(src, setup_body(src)) == src


def test_replace_adds_a_block_to_a_notebook_without_one():
    """The block goes right after `app = marimo.App(...)`, where marimo writes it."""
    src = "import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _():\n    return\n"
    out = replace_setup_body(src, 'main_name = "New"\n')
    assert out == (
        "import marimo\n\napp = marimo.App()\n\n"
        'with app.setup:\n    main_name = "New"\n'
        "\n\n@app.cell\ndef _():\n    return\n"
    )


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("import flyte\nmain_name = (\n", "line 2"),
        ("main_name = 3\n", "main_name"),
    ],
)
def test_replace_refuses_a_body_that_would_break(body, error):
    """A bad edit is refused with the reason, in the editor's line numbers."""
    with pytest.raises(SetupError, match=error):
        replace_setup_body(_notebook(), body)


def test_with_setup_values_replaces_a_declared_value():
    """Create and copy set the name over the seed's own."""
    src = with_setup_values(_notebook(), main_name='Say "hi"')
    assert notebook_name(src) == 'Say "hi"'
    assert notebook_description(src) == "Quality control."


def test_with_setup_values_declares_a_missing_value_after_the_imports():
    """A value the block lacks gets its own line after the imports, before the rest."""
    setup = "with app.setup:\n    import flyte\n\n    main_env = notebook_env\n"
    src = with_setup_values(_notebook(setup), main_name="QC")
    assert setup_body(src) == (
        'import flyte\n\nmain_name = "QC"\n\nmain_env = notebook_env\n'
    )


def test_with_setup_values_adds_a_block_when_there_is_none():
    """A notebook without a setup block (a shipped workflow) gets one."""
    src = "import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _():\n    return\n"
    out = with_setup_values(src, main_name="scRNA-seq", main_description="UMAPs.")
    assert notebook_name(out) == "scRNA-seq"
    assert notebook_description(out) == "UMAPs."
