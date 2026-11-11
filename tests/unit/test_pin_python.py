"""Tests for `pin_python` and `use_image_sdk`, which fix up a notebook's header
for pixi's sandbox before the launch script starts marimo.

A header without a Python pin gets conda-forge's newest in pixi's sandbox,
which marimo's own packages may not be built for, and the kernel never starts.
A header that sources `stargazer-bio` only in `[tool.uv.sources]` gets the SDK
from PyPI there, since pixi doesn't read that table.
"""

import re
import sys
import tomllib

from conftest import load_proxy

proxy = load_proxy()

HEADER = re.compile(r"(?m)^# /// script$\s(?P<content>(^#(| .*)$\s)+)^# ///$")

PIN = f"{sys.version_info.major}.{sys.version_info.minor}.*"
BODY = "import marimo\n\napp = marimo.App()\n"


def header(text: str) -> dict:
    """The notebook's PEP 723 header, parsed."""
    content = HEADER.search(text).group("content")
    return tomllib.loads(
        "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in content.splitlines(keepends=True)
        )
    )


OLD_HEADER = (
    "# /// script\n"
    '# requires-python = ">=3.14"\n'
    "# dependencies = [\n"
    '#   "stargazer-bio",\n'
    "# ]\n"
    "#\n"
    "# [tool.uv.sources]\n"
    '# stargazer-bio = { path = "/stargazer", editable = true }\n'
    "# ///\n"
)


def test_an_old_uv_header_gains_a_python_pin_and_keeps_the_rest(tmp_path):
    """A header with no pixi table gets one before its close, other keys intact."""
    original = (
        "# /// script\n"
        '# requires-python = ">=3.14"\n'
        "# dependencies = [\n"
        '#   "stargazer-bio",\n'
        "# ]\n"
        "#\n"
        "# [tool.uv.sources]\n"
        '# stargazer-bio = { path = "/stargazer", editable = true }\n'
        "# ///\n" + BODY
    )
    path = tmp_path / "notebook.py"
    path.write_text(original)

    proxy.pin_python(path)

    text = path.read_text()
    parsed = header(text)
    assert parsed["tool"]["pixi"]["dependencies"] == {"python": PIN}
    assert parsed["dependencies"] == ["stargazer-bio"]
    assert parsed["tool"]["uv"]["sources"]["stargazer-bio"]["path"] == "/stargazer"
    assert text.endswith("# ///\n" + BODY)
    inserted = f'#\n# [tool.pixi.dependencies]\n# python = "{PIN}"\n# ///'
    assert text.replace(inserted, "# ///", 1) == original


def test_a_pixi_table_without_python_gets_the_pin_after_it(tmp_path):
    """The pin goes directly after the table header, beside what it already lists."""
    original = (
        '# /// script\n# [tool.pixi.dependencies]\n# samtools = "*"\n# ///\n' + BODY
    )
    path = tmp_path / "notebook.py"
    path.write_text(original)

    proxy.pin_python(path)

    text = path.read_text()
    assert header(text)["tool"]["pixi"]["dependencies"] == {
        "python": PIN,
        "samtools": "*",
    }
    assert len(text.splitlines()) == len(original.splitlines()) + 1


def test_a_header_that_already_pins_python_is_left_alone(tmp_path):
    """A pinned header is not rewritten, byte for byte."""
    original = (
        '# /// script\n# [tool.pixi.dependencies]\n# python = "3.13.*"\n# ///\n' + BODY
    )
    path = tmp_path / "notebook.py"
    path.write_bytes(original.encode())

    proxy.pin_python(path)

    assert path.read_bytes() == original.encode()


def test_a_notebook_without_a_header_gets_one_prepended(tmp_path):
    """A headerless notebook keeps its text after a whole new header."""
    path = tmp_path / "notebook.py"
    path.write_text(BODY)

    proxy.pin_python(path)

    text = path.read_text()
    assert header(text)["tool"]["pixi"]["dependencies"] == {"python": PIN}
    assert text.endswith(BODY)


def test_a_missing_file_stays_missing(tmp_path):
    """Nothing is created for a notebook that isn't there."""
    path = tmp_path / "gone.py"

    proxy.pin_python(path)

    assert not path.exists()


def test_pinning_twice_changes_nothing_the_second_time(tmp_path):
    """The second call sees the first call's pin and leaves the text alone."""
    original = (
        "# /// script\n"
        '# requires-python = ">=3.14"\n'
        "# dependencies = [\n"
        '#   "stargazer-bio",\n'
        "# ]\n"
        "# ///\n" + BODY
    )
    path = tmp_path / "notebook.py"
    path.write_text(original)
    proxy.pin_python(path)
    once = path.read_text()

    proxy.pin_python(path)

    assert path.read_text() == once


def test_an_old_uv_source_is_copied_where_pixi_reads_it(tmp_path):
    """The uv source's path lands in pixi's PyPI table; the uv table stays."""
    path = tmp_path / "notebook.py"
    path.write_text(OLD_HEADER + BODY)

    proxy.use_image_sdk(path)

    text = path.read_text()
    parsed = header(text)
    assert parsed["tool"]["pixi"]["pypi-dependencies"] == {
        "stargazer-bio": {"path": "/stargazer"}
    }
    assert parsed["tool"]["uv"]["sources"]["stargazer-bio"] == {
        "path": "/stargazer",
        "editable": True,
    }
    assert text.endswith("# ///\n" + BODY)


def test_the_launch_steps_together_fix_an_old_header(tmp_path):
    """Pinning Python then copying the source leaves both in pixi's tables."""
    path = tmp_path / "notebook.py"
    path.write_text(OLD_HEADER + BODY)

    proxy.pin_python(path)
    proxy.use_image_sdk(path)

    pixi = header(path.read_text())["tool"]["pixi"]
    assert pixi["dependencies"] == {"python": PIN}
    assert pixi["pypi-dependencies"] == {"stargazer-bio": {"path": "/stargazer"}}


def test_a_header_pixi_already_sources_is_left_alone(tmp_path):
    """A header with the SDK in pixi's PyPI table is not rewritten."""
    original = (
        "# /// script\n"
        "# [tool.uv.sources]\n"
        '# stargazer-bio = { path = "/elsewhere" }\n'
        "#\n"
        "# [tool.pixi.pypi-dependencies]\n"
        '# stargazer-bio = { path = "/stargazer" }\n'
        "# ///\n" + BODY
    )
    path = tmp_path / "notebook.py"
    path.write_bytes(original.encode())

    proxy.use_image_sdk(path)

    assert path.read_bytes() == original.encode()


def test_a_header_without_a_uv_source_is_left_alone(tmp_path):
    """Nothing to copy, nothing written."""
    original = '# /// script\n# dependencies = ["stargazer-bio"]\n# ///\n' + BODY
    path = tmp_path / "notebook.py"
    path.write_bytes(original.encode())

    proxy.use_image_sdk(path)

    assert path.read_bytes() == original.encode()


def test_a_uv_source_without_a_path_is_left_alone(tmp_path):
    """Only a path source names the image's SDK; a git source isn't copied."""
    original = (
        "# /// script\n"
        "# [tool.uv.sources]\n"
        '# stargazer-bio = { git = "https://example.com/x.git" }\n'
        "# ///\n" + BODY
    )
    path = tmp_path / "notebook.py"
    path.write_bytes(original.encode())

    proxy.use_image_sdk(path)

    assert path.read_bytes() == original.encode()


def test_use_image_sdk_creates_no_missing_file(tmp_path):
    """Nothing is created for a notebook that isn't there."""
    path = tmp_path / "gone.py"

    proxy.use_image_sdk(path)

    assert not path.exists()
