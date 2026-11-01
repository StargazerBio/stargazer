---
title: agent-wiki
status: review
priority: normal
created: 2026-11-01
pr: 118
---

Turn the agent reference (`.claude/reference/`) into a wiki in the Karpathy LLM-wiki pattern, with Obsidian wikilinks, viewable in the same vault as this board.

- [x] `.claude/reference/` becomes `.claude/context/` on `main`: `raw/` holds the sources as captured (Flyte v2 docs and SDK examples, marimo's sandbox guide, tool help), and the pages are synthesized from them and the code, catalogued in [[index]]
- [x] The Flyte sources become [[flyte]] and a page per concept, the marimo guide [[marimo-sandbox]], and the tool help [[tool-help]], [[gatk]] and [[parabricks]]
- [x] Stargazer's own internals stay out of the wiki, since a second copy of a code fact drifts: the three `*_internals.md` files' facts were nearly all in docstrings and comments already, and the rest move there (`runtime/proxy.py`, `notebooks/__init__.py`, `release.yml`, `asset.py`, `pinata.py`). Each page's `## In Stargazer` points at code rather than restating it
- [x] Every file name unique, so `[[name]]` resolves: tool help is `<tool>/<tool>-<subcommand>.md`, and the capture script names new files that way. The misfiled bwa and samtools manuals move out of `parabricks/`
- [x] The `wiki` skill holds the schema and the query, ingest and lint operations; `cli/wiki_lint.py` is lint's mechanical half, in pre-commit, with unit tests
- [x] The lint warns, without failing, about a page whose `sources` name a file the branch changes while the page is untouched
- [x] AGENTS.md, the write-docs and tasks-and-workflows skills and the architecture docs point at the wiki
- [x] This branch's worktree moves inside the wiki, to `.claude/context/planning/` (gitignored on `main`), so `.claude/context` is one Obsidian vault holding the wiki and the board. The lint checks that no ticket's name matches a page's
- [ ] Opened in Obsidian: the board unchanged, the wiki's links and heading links resolving, the graph view connecting tickets that link wiki pages

No `log.md`: AGENTS.md keeps history out of durable docs, and git has it.

## Verification recipe

1. `uv run python cli/wiki_lint.py` on the branch exits 0; breaking a heading link and moving a raw file makes it name both. Calling its `stale()` with `src/stargazer/config.py` and a file under `src/stargazer/workflows/` as changed names the pages citing each.
2. `uv run --all-extras pytest -q tests/unit/test_wiki_lint.py` passes (15 tests).
3. With the branch merged and pulled, and the worktree moved (`git worktree move planning .claude/context/planning` in the main checkout), `git check-ignore .claude/context/planning/<ticket>.md` names the ignore rule, and Obsidian opened on `$MAIN/.claude/context` shows the board and the wiki with their links resolving.
