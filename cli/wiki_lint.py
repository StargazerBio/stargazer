#!/usr/bin/env python3
"""
Lint the agent wiki in `.claude/wiki/`, the mechanical half of the `wiki` skill's lint.

Checks that every [[wikilink]] (and its #heading) resolves the way Obsidian
would resolve it, every page is in index.md, every raw source is cited by some
page, every code path a page lists in `sources` exists, no two files share a
name, and no page has the `status` property the ticket board groups on.
Raw sources are captured verbatim, so their own links aren't checked.

It also warns, without failing, about pages that may have gone stale: a page
whose `sources` name a file this branch changes (against its merge base with
`origin/main`, uncommitted changes included) when the branch leaves the page
itself alone. The page may well still hold; the warning says to reread it.

Usage: uv run python cli/wiki_lint.py
"""

import re
import subprocess
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


def stale(wiki: Path, repo: Path, changed: set[str]) -> list[str]:
    """Pages citing a file in `changed` (repo-relative paths) that aren't in it.

    A source that's a directory covers every file under it.
    """
    files = {p.stem: p for p in wiki.rglob("*.md")}
    warnings = []
    for path in sorted(wiki.glob("*.md")):
        if str(path.relative_to(repo)) in changed:
            continue
        for source in _sources(_split(path.read_text())[0]):
            if m := LINK.fullmatch(source):
                target = files.get(Path(m.group(1).strip()).name)
                if target is None:
                    continue
                source = str(target.relative_to(repo))
            if source in changed:
                warnings.append(
                    f"{path.name} cites {source}, which this branch changes"
                )
            elif inside := sorted(c for c in changed if c.startswith(source + "/")):
                warnings.append(
                    f"{path.name} cites {source}, which this branch changes "
                    f"({', '.join(inside)})"
                )
    return warnings


def _changed(repo: Path) -> set[str] | None:
    """Files this branch changes against `origin/main`, or None without one."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
        ).stdout

    try:
        base = git("merge-base", "HEAD", "origin/main").strip()
        return set(git("diff", "--name-only", base).split())
    except subprocess.CalledProcessError:
        return None


def main() -> int:
    """Lint the repo's wiki, print its problems, and warn of stale pages."""
    repo = Path(__file__).resolve().parents[1]
    wiki = repo / ".claude" / "wiki"
    problems = lint(wiki, repo)
    for problem in problems:
        print(problem)
    changed = _changed(repo)
    if warnings := stale(wiki, repo, changed or set()):
        print("Reread these pages: each cites a file this branch changes.")
        for warning in warnings:
            print(f"  {warning}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
