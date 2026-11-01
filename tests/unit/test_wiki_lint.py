"""
Tests for the agent wiki's lint (`cli/wiki_lint.py`), on small wikis built in tmp_path.
"""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "wiki_lint", REPO / "cli" / "wiki_lint.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint = _load().lint
stale = _load().stale


@pytest.fixture
def wiki(tmp_path):
    """A clean wiki: an index, one page citing one raw source and one code path."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text("")
    root = tmp_path / "wiki"
    (root / "raw").mkdir(parents=True)
    (root / "raw" / "source-doc.md").write_text("# Source\n\n## Part one\n")
    (root / "index.md").write_text("# Index\n\n- [[page]]\n- [[source-doc]]\n")
    (root / "page.md").write_text(
        "---\nsources:\n"
        '  - "[[source-doc]]"\n'
        "  - src/mod.py\n"
        "---\n\n# Page\n\nSee [[source-doc#Part one|part one]].\n"
    )
    return root


def _write(root: Path, name: str, text: str) -> None:
    (root / name).write_text(text)


def test_clean_wiki_has_no_problems(wiki):
    assert lint(wiki, wiki.parent) == []


def test_link_to_missing_page(wiki):
    _write(wiki, "page.md", "# Page\n\n[[nowhere]]\n")
    assert lint(wiki, wiki.parent) == ["page.md: [[nowhere]] names no page"]


def test_link_to_missing_heading(wiki):
    _write(wiki, "page.md", "# Page\n\n[[source-doc#Part two]]\n")
    assert lint(wiki, wiki.parent) == [
        "page.md: [[source-doc#Part two]] names no heading in source-doc"
    ]


def test_links_in_code_are_not_links(wiki):
    _write(
        wiki,
        "page.md",
        "# Page\n\n[[source-doc]] and `[[tool.uv.index]]`\n\n```\n[[nowhere]]\n```\n",
    )
    assert lint(wiki, wiki.parent) == []


def test_heading_inside_code_is_not_a_heading(wiki):
    _write(wiki / "raw", "source-doc.md", "# Source\n\n```python\n# comment\n```\n")
    _write(wiki, "page.md", "# Page\n\n[[source-doc#comment]]\n")
    assert lint(wiki, wiki.parent) == [
        "page.md: [[source-doc#comment]] names no heading in source-doc"
    ]


def test_page_missing_from_index(wiki):
    _write(wiki, "other.md", "# Other\n\n[[page]]\n")
    assert lint(wiki, wiki.parent) == ["other.md: not listed in index.md"]


def test_raw_source_no_page_links(wiki):
    _write(wiki / "raw", "unread.md", "# Unread\n")
    assert lint(wiki, wiki.parent) == ["raw/unread.md: no page links it"]


def test_source_path_that_does_not_exist(wiki):
    _write(wiki, "page.md", "---\nsources:\n  - src/gone.py\n---\n\n[[source-doc]]\n")
    assert lint(wiki, wiki.parent) == ["page.md: source src/gone.py doesn't exist"]


def test_status_property_would_put_a_page_on_the_board(wiki):
    _write(wiki, "page.md", "---\nstatus: done\n---\n\n[[source-doc]]\n")
    assert lint(wiki, wiki.parent) == [
        "page.md: has a status property, which puts it on the ticket board"
    ]


def test_duplicate_basenames(wiki):
    (wiki / "raw" / "sub").mkdir()
    _write(wiki / "raw" / "sub", "page.md", "# Shadow\n")
    _write(wiki, "index.md", "# Index\n\n- [[page]]\n- [[source-doc]]\n")
    assert "raw/sub/page.md: shares its name with page.md" in lint(wiki, wiki.parent)


def test_page_citing_a_changed_file_is_stale(wiki):
    assert stale(wiki, wiki.parent, {"src/mod.py"}) == [
        "page.md cites src/mod.py, which this branch changes"
    ]


def test_page_changed_alongside_its_source_is_not_stale(wiki):
    assert stale(wiki, wiki.parent, {"src/mod.py", "wiki/page.md"}) == []


def test_changed_raw_source_makes_its_pages_stale(wiki):
    assert stale(wiki, wiki.parent, {"wiki/raw/source-doc.md"}) == [
        "page.md cites wiki/raw/source-doc.md, which this branch changes"
    ]


def test_directory_source_covers_the_files_in_it(wiki):
    _write(wiki, "page.md", "---\nsources:\n  - src\n---\n\n[[source-doc]]\n")
    assert stale(wiki, wiki.parent, {"src/mod.py"}) == [
        "page.md cites src, which this branch changes (src/mod.py)"
    ]


def test_unrelated_change_makes_nothing_stale(wiki):
    assert stale(wiki, wiki.parent, {"README.md"}) == []
