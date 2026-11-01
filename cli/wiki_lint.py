#!/usr/bin/env python3
"""
Lint the agent wiki in `.claude/wiki/`, the mechanical half of the `wiki` skill's lint.

Checks that every [[wikilink]] (and its #heading) resolves the way Obsidian
would resolve it, every page is in index.md, every raw source is cited by some
page, every code path a page lists in `sources` exists, no two files share a
name, and no page has the `status` property the ticket board groups on.
Raw sources are captured verbatim, so their own links aren't checked.

Usage: uv run python cli/wiki_lint.py
"""

import re
import sys
from pathlib import Path

LINK = re.compile(r"\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|[^\]]*)?\]\]")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _split(text: str) -> tuple[str, str]:
    """Split a file into its frontmatter block and its body."""
    m = FRONTMATTER.match(text)
    return (m.group(1), text[m.end() :]) if m else ("", text)


def _prose(text: str) -> str:
    """The text with fenced and inline code removed, where nothing is a link."""
    return INLINE_CODE.sub("", FENCE.sub("", text))


def _headings(text: str) -> set[str]:
    """Every markdown heading outside code fences."""
    return {
        m.group(1)
        for line in FENCE.sub("", _split(text)[1]).splitlines()
        if (m := HEADING.match(line))
    }


def _sources(frontmatter: str) -> list[str]:
    """The entries of the frontmatter's `sources` list, unquoted."""
    entries, inside = [], False
    for line in frontmatter.splitlines():
        if not line.startswith(" "):
            inside = line.startswith("sources:")
        elif inside and line.strip().startswith("- "):
            entries.append(line.strip()[2:].strip().strip("\"'"))
    return entries


def lint(wiki: Path, repo: Path) -> list[str]:
    """Return the wiki's problems, one line each."""
    problems = []
    files = sorted(wiki.rglob("*.md"), key=lambda p: str(p.relative_to(wiki)))
    by_name: dict[str, Path] = {}
    for path in files:
        if path.stem in by_name:
            problems.append(
                f"{path.relative_to(wiki)}: shares its name with "
                f"{by_name[path.stem].relative_to(wiki)}"
            )
        else:
            by_name[path.stem] = path

    linked: set[str] = set()
    for path in files:
        rel = path.relative_to(wiki)
        if rel.parts[0] == "raw":
            continue
        frontmatter, body = _split(path.read_text())
        if re.search(r"^status:", frontmatter, re.MULTILINE):
            problems.append(
                f"{rel}: has a status property, which puts it on the ticket board"
            )
        for source in _sources(frontmatter):
            if not source.startswith("[[") and not (repo / source).exists():
                problems.append(f"{rel}: source {source} doesn't exist")
        for m in LINK.finditer(frontmatter + "\n" + _prose(body)):
            name = Path(m.group(1).strip()).name.removesuffix(".md")
            heading = m.group(2)
            target = by_name.get(name)
            linked.add(name)
            if target is None:
                problems.append(f"{rel}: {m.group(0)} names no page")
            elif heading and heading.strip() not in _headings(target.read_text()):
                problems.append(f"{rel}: {m.group(0)} names no heading in {name}")

    index = wiki / "index.md"
    listed = {
        Path(m.group(1).strip()).name for m in LINK.finditer(_prose(index.read_text()))
    }
    for path in files:
        rel = path.relative_to(wiki)
        if rel.parts[0] == "raw":
            if path.stem not in linked:
                problems.append(f"{rel}: no page links it")
        elif path != index and path.stem not in listed:
            problems.append(f"{rel}: not listed in index.md")
    return problems


def main() -> int:
    """Lint the repo's wiki and print its problems."""
    repo = Path(__file__).resolve().parents[1]
    problems = lint(repo / ".claude" / "wiki", repo)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
