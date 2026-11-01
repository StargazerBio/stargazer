---
name: wiki
description: "Read, add to and check the agent wiki in .claude/wiki/: Stargazer's internals beneath docs/architecture/, Flyte, marimo and the bioinformatics tools tasks wrap, as interlinked pages synthesized from raw sources. Use when you need reference on any of those, after changing code a wiki page describes, or when adding a new source such as a tool's help or a framework's docs."
---

# The agent wiki

`.claude/wiki/` is the agents' knowledge base, kept the way Karpathy's LLM wiki is: raw sources that are never edited, and pages synthesized from them and from the code, which agents write and keep current. It's plain markdown with Obsidian `[[wikilinks]]`, and it's tracked on `main`, so a page changes in the same branch as the code it describes. The `planning` branch carries a `wiki` symlink to it, so the Obsidian vault at `$MAIN/planning` shows the wiki beside the ticket board.

## Layout

- **`index.md`** lists every page with a one-line summary, by topic. Start every lookup there.
- **Pages** sit flat at the top: a Stargazer subsystem (each the companion of a `docs/architecture/` doc), a framework concept, or a tool.
- **`raw/`** holds the sources exactly as captured: framework docs, tool help (`raw/tool-help/`, with the script that captures it). Read them for detail and examples; never edit their content.

## Page conventions

- **One topic per page, named in kebab-case.** Every file's name is unique across the wiki, raw sources included, so `[[name]]` always resolves without a path.
- **Frontmatter lists `sources`**: the raw sources as quoted wikilinks (`"[[flyte-v2-docs]]"`) and the repo files it describes as repo-relative paths. That list is how an ingest finds the pages a changed source touches. Never give a page a `status` property: the ticket board shows any note that has one.
- **A `# Title`, then one paragraph** saying what the page covers and pointing at the raw source for detail.
- **Facts as bold-led bullets**, each a present-tense statement of how things are. No history, no "now" or "used to": that's in git.
- **Link generously.** Link a concept's page wherever it's mentioned, a raw source's section with `[[source#Heading]]`, and end a page with `## Related`. Code and docs outside the wiki are named as backticked paths; the vault can't open them.
- **No code blocks.** Examples stay in the raw sources; a page names the API inline and links the section that shows it.
- **Stargazer specifics under `## In Stargazer`** on a framework or tool page, checked against the code.
- **Agent-facing, not product-facing.** Internals, env vars and vendor names belong here; a gap or deferred work is a ticket, not a page.

## Operations

### Query

Read `index.md`, then the pages it points at, following their links and dropping into `raw/` for detail. When the answer took real digging and will be wanted again, write it back as a page or a section of one.

### Ingest

When a source arrives (a new tool's help, a framework's updated docs) or code a page describes changes:

1. A new source goes in `raw/` under a unique kebab-case name. Tool help is captured with `raw/tool-help/generate_help_docs.sh`, in the image that has the tool (the `tool-help` page says how).
2. Find the pages it touches: `grep -l` the source's name or path in the pages' `sources`.
3. Update each one, and add a page when a topic has none. A new page goes into `index.md`.
4. Where a source contradicts a page, the code decides; fix the page, and note on it when a raw source is itself wrong.

A change to a subsystem updates its page in the same branch, the way it updates its `docs/architecture/` doc.

### Lint

`uv run python cli/wiki_lint.py` checks what can be checked mechanically, and runs in pre-commit: links and headings resolve, every page is in the index, every raw source is cited, every source path exists, no name is shared, no page has `status`. The rest is yours when you touch a page: a claim the code no longer bears out, two pages that disagree, a topic mentioned on several pages that has no page of its own, a page nothing links to but the index.
