"""Tests for subprocess utilities."""

from pathlib import Path

import pytest

from stargazer.utils.subprocess import _run


async def test_args_of_any_type_are_passed_as_strings(tmp_path):
    """A Path as the command or an argument, and an int, all reach the process."""
    lines = tmp_path / "lines.txt"
    lines.write_text("line 1\nline 2\nline 3\n")
    head = Path((await _run(["which", "head"]))[0].strip())

    stdout, stderr = await _run([head, "-n", 2, lines])

    assert (stdout, stderr) == ("line 1\nline 2\n", "")


@pytest.mark.parametrize("as_str", [False, True], ids=["path", "str"])
async def test_cwd_sets_the_working_directory(tmp_path, as_str):
    work = tmp_path / "work"
    work.mkdir()
    (work / "testfile.txt").write_text("content\n")

    stdout, _ = await _run(["ls"], cwd=str(work) if as_str else work)

    assert stdout == "testfile.txt\n"


async def test_stderr_is_returned_on_success():
    assert await _run(["sh", "-c", "echo out; echo err >&2"]) == ("out\n", "err\n")


async def test_failure_raises_with_the_exit_code_and_stderr():
    with pytest.raises(RuntimeError, match=r"failed with code 3[\s\S]*boom"):
        await _run(["sh", "-c", "echo boom >&2; exit 3"])
