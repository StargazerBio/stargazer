---
name: wiki
description: "Read, add to and check the agent wiki in .claude/wiki/: what Stargazer builds on (Flyte, marimo and the bioinformatics tools tasks wrap), as interlinked pages synthesized from raw sources. Use when you need reference on any of those, when the wiki lint warns that a page cites a file you changed, or when adding a new source such as a tool's help or a framework's docs."
---

# The agent wiki

`.claude/wiki/` is the agents' knowledge of what Stargazer builds on, kept the way Karpathy's LLM wiki is: raw sources that are never edited, and pages synthesized from them, which agents write and keep current. It's plain markdown with Obsidian `[[wikilinks]]`, tracked on `main`. The `planning` branch carries a `wiki` symlink to it, so the Obsidian vault at `$MAIN/planning` shows the wiki beside the ticket board.

## What goes where

- **A fact about Stargazer's own code** goes in a docstring or comment at that code, where a diff that changes the code shows it. One that spans modules goes in `docs/architecture/`. Neither goes in the wiki: a second copy of a code fact drifts.
- **Knowledge from outside** (a framework's model and API, a tool's parameters) goes in the wiki, with its source in `raw/`.
- **Where Stargazer meets an outside concept**, a page's `## In Stargazer` section points at the code that uses it (a module, a function, the comment that explains it), without restating what that code says.

## Layout

- **`index.md`** lists every page with a one-line summary, by topic. Start every lookup there.
- **Pages** sit flat at the top: a framework concept or a tool.
- **`raw/`** holds the sources exactly as captured: framework docs, tool help (`raw/tool-help/`, with the script that captures it). Read them for detail and examples; never edit their content.

## Page conventions

- **One topic per page, named in kebab-case.** Every file's name is unique across the vault, raw sources and tickets included, so `[[name]]` always resolves without a path.
- **Frontmatter lists `sources`**: the raw sources as quoted wikilinks (`"[[flyte-v2-docs]]"`) and the repo files or directories the page points at, as repo-relative paths. The lint uses the list to say when a page may have gone stale, so list what the page depends on and nothing broader. Never give a page a `status` property: the ticket board shows any note that has one.
- **A `# Title`, then one paragraph** saying what the page covers and pointing at the raw source for detail.
- **Facts as bold-led bullets**, each a present-tense statement of how things are. No history, no "now" or "used to": that's in git.
- **Link generously.** Link a concept's page wherever it's mentioned, a raw source's section with `[[source#Heading]]`, and end a page with `## Related`. Code and docs outside the wiki are named as backticked paths; the vault can't open them. A heading with a `/` in it can't be linked; link the section above it.
- **No code blocks.** Examples stay in the raw sources; a page names the API inline and links the section that shows it.
- **A gap or deferred work is a ticket**, not a page or a note on one.

## Operations

### Query

Read `index.md`, then the pages it points at, following their links and dropping into `raw/` for detail. When the answer took real digging and will be wanted again, write it back as a page or a section of one.

### Ingest

When a source arrives (a new tool's help, a framework's updated docs):

1. It goes in `raw/` under a unique kebab-case name. Tool help is captured with `raw/tool-help/generate_help_docs.sh`, in the image that has the tool (the `tool-help` page says how).
2. Find the pages it touches: `grep -l` the source's name in the pages' `sources`.
3. Update each one, and add a page when a topic has none. A new page goes into `index.md`.
4. Where a source contradicts a page, the installed package or tool decides; fix the page, and note on it when a raw source is itself wrong.

### Lint

`uv run python cli/wiki_lint.py` runs in pre-commit. It fails on what can be checked mechanically: links and headings resolve, every page is in the index, every raw source is cited, every source path exists, no name is shared, no page has `status`. It also warns, without failing, about each page whose `sources` include a file the branch changes while the page is unchanged. Reread each one it names and fix what no longer holds; a page that still holds needs no edit, and the warning lasts until the branch merges.

The rest is yours when you touch a page: a claim the code no longer bears out, two pages that disagree, a topic mentioned on several pages that has no page of its own, an `## In Stargazer` bullet that restates code instead of pointing at it.
