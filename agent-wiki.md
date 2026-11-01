---
title: agent-wiki
status: doing
priority: normal
created: 2026-11-01
---

Turn the agent reference (`.claude/reference/`) into a wiki in the Karpathy LLM-wiki pattern, with Obsidian wikilinks, viewable in the same vault as this board.

- [x] `.claude/reference/` becomes `.claude/wiki/` on `main`: `raw/` holds the sources as captured (Flyte v2 docs and SDK examples, marimo's sandbox guide, tool help), and the pages are synthesized from them and the code, catalogued in [[index]]
- [x] The three `*_internals.md` companions become [[runtime]], [[notebooks]], [[storage]], [[provenance]] and [[images]]; the Flyte sources become [[flyte]] and a page per concept; the tool help gets [[tool-help]], [[gatk]] and [[parabricks]]
- [x] Every file name unique, so `[[name]]` resolves: tool help is `<tool>/<tool>-<subcommand>.md`, and the capture script names new files that way. The misfiled bwa and samtools manuals move out of `parabricks/`
- [x] The `wiki` skill holds the schema and the query, ingest and lint operations; `cli/wiki_lint.py` is lint's mechanical half, in pre-commit, with unit tests
- [x] AGENTS.md, the write-docs and tasks-and-workflows skills and the architecture docs point at the wiki
- [x] This branch carries `wiki`, a symlink to `../.claude/wiki`, so opening `$MAIN/planning` in Obsidian shows the board and the wiki together
- [ ] Opened in Obsidian: the board unchanged, the wiki's links and heading links resolving, the graph view connecting tickets that link wiki pages

No `log.md`: AGENTS.md keeps history out of durable docs, and git has it.

## Verification recipe

1. `uv run python cli/wiki_lint.py` on the branch exits 0; breaking a heading link and moving a raw file makes it name both.
2. `uv run --all-extras pytest -q tests/unit/test_wiki_lint.py` passes.
3. With the branch merged and pulled in the main checkout, `ls $MAIN/planning/wiki/index.md` resolves through the symlink, and Obsidian opened on `$MAIN/planning` shows the board and a `wiki` folder whose links resolve.
