# Stargazer

**General Guidelines**
- When I say task, I am referring to a Flyte V2 task, not a raw python function
- Tasks are collected into workflows which are just regular tasks calling other tasks, sync or async
- This project uses UV so the appropriate commands are `uv add` and `uv pip install -e .`
- If something is changed that you didn't change, it's not a typo, it's a manual change. I do still write code occassionally..
- Don't use the "if TYPE_CHECKING:" pattern anywhere, Flyte will always check types
- The README is a document written exclusively BY HUMANS FOR HUMANS. Never modify the README. Notify if it is out of spec only.

**Git Workflow**
- Every change gets its own worktree, on its own branch cut from an up-to-date `origin/main`. Name the branch after the change in short kebab-case (e.g. `fix/scrna-oom`, `docs/branch-pr-workflow`) and the worktree after its slug, under `.claude/worktrees/` (gitignored): `git fetch origin && git worktree add --no-track .claude/worktrees/scrna-oom -b fix/scrna-oom origin/main`. Claude Code's `EnterWorktree` makes them in the same place. All work happens in the worktree; the main checkout stays on a clean `main`. Never commit directly to `main`
- A new worktree has none of the gitignored local state. `uv run` builds it its own `.venv`, but link the rest from the main checkout as the work needs it: `.flyte/config.yaml` and `.flyte/union.yaml` for anything that talks to Flyte (devbox tier, deploys), `tests/.secrets` for the pinata tier, `.env` for `devbox/setup.sh` (it reads `PINATA_JWT` from it, and without one the devbox's secret is left empty). From the worktree root: `MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")`, then `mkdir -p .flyte && ln -s "$MAIN"/.flyte/{config,union}.yaml .flyte/`, `ln -s "$MAIN/tests/.secrets" tests/.secrets` and `ln -s "$MAIN/.env" .env`
- One change per worktree. An unrelated fix spotted along the way gets its own worktree and PR, or a ticket
- Small doc-only edits (a rule in this file, a stale reference in `docs/` or a wiki page) don't get their own PR. Commit them on whichever branch is in progress or next to open, related or not, and list them under their own heading in that PR's description
- Follow-up work on a branch that is still unmerged (changes to the same feature, fixes, or review feedback) is committed in that branch's worktree, not on a new branch cut from it. Keep the merge tree flat: a new branch is only for a new, independent change cut from `main`
- Commit on the branch as the work progresses; no need to ask first. Never force-push `main`
- When the change is done (tests pass, verified on its real surface), push the branch and open a PR against `main` with `gh pr create`. The description says what changed and why, the verification evidence, and anything deferred
- The PR is where human review happens. Never merge a PR yourself — the user reviews and merges it. Review feedback is addressed with further commits on the same branch
- A PR description stays true to its branch. Whenever pushes make it drift (the image's name, what was verified, what's deferred, the list of changes), rewrite it in the same step with `gh pr edit --body-file`, from the branch's current state. Don't post PR comments or replies; explanations of a change belong in its commit message
- Once the PR is merged, read its comments and reviews (`gh pr view <n> --json comments,reviews`), the comment left at merge included. Answer each follow-up raised there: urgent ones (a break on the tenant or in `main`, a bug users are hitting) get their own branch cut from `origin/main` straight away; the rest become tickets, named in the merged ticket's `## Outcome`. Then remove its worktree (`git worktree remove .claude/worktrees/<slug>`), delete the branch, and `git pull` in the main checkout. New worktrees branch from `origin/main` and don't need it, but sessions started in the main checkout read this file and the skills from it

**Positioning**
- The marimo notebook is Stargazer's primary user surface for both experimentation (`marimo edit`) and reproducible production (`marimo run`) — it's the most approachable entry point, so default new feature designs to the notebook surface (marimo, `mo.ui`) over CLI or other entry points. The SDK (`src/stargazer/tasks/`, `src/stargazer/workflows/`) is a first-class user surface too: authoring workflows in an IDE by importing SDK tasks directly is a fully supported use case, not a maintainer-only path.
- This repo is the pod side: `src/stargazer/` is the bioinformatics SDK (tasks, workflows, assets, TaskEnvironment configs, notebooks), published as `stargazer-bio`, and `runtime/` is what runs in a notebook pod around it (the proxy, the launch script, the image recipe). A release publishes both, the package and the image, under one calendar tag. The pod manager side is the `StargazerBio/infra` repo: the dashboard, its deploy, onboarding, the AWS stacks and the devbox's dashboard, pinned to a release. A dashboard route, an AppEnvironment for a hosted service, a deploy entrypoint or an auth integration for the dashboard goes there. What a release promises it is the pod contract in `docs/architecture/runtime.md`.

**Dev Process**
- You will implement features piece by piece in a sequential fashion
- Handle a single case well at first instead of trying to anticipate every way the app will be used
- Do not add complexity until it is needed, which may be never
- Simple tests will be written before implementation, then implementation follows without pausing for test review. Since no human checks the tests up front, they have to check themselves:
  - Run each new test before implementing and confirm it fails for the expected reason (missing behavior, not an import error or broken fixture)
  - Assert observable behavior against literal expected values. If a test would still pass when the code under test returns `None`, rewrite the assertion or delete the test
  - Don't restate configuration in a test. A version pin, a resource size or any other chosen value changes with the choice, so a test that hardcodes it only gets edited alongside it. Check what the value does on its real surface instead
  - Prefer no new test over a bad test. When a real test would need heavy mocking, production-only state, or slow infrastructure for a small change, use the closest real check instead (a local Flyte run, a script, a repro command), run it before and after the change, and say so
- The review checkpoint is the pull request. The user reviews every PR before merging, so tests and implementation are reviewed together in its diff
- Implementation will be tightly scoped so it can be understood
- Tests will run until they pass
- Passing tests are not proof a feature works. Before declaring user-facing work done, drive it on its real surface with the `verify-stargazer` skill, and report the evidence
- Every claim in a report carries its evidence or a label: measured, inferred, or guess. Never hand the user a check you could run yourself
- Tear down what testing starts on the Union tenant as soon as its check is done. Scale-to-zero won't do it for you: an idle app holds its pod and node for its whole `scaledown_after` (an hour for the dashboard). Stop every app you deployed or woke, including probes, notebook apps and the test account's dashboard (`flyte --config .flyte/union.yaml update app <name> --deactivate -p <project> -d development`), and abort any run still going (`flyte --config .flyte/union.yaml abort run <name> -p <project> -d development`). Before reporting, list apps and live runs (`get app`, `get run --in-phase running`) in every project you touched and confirm nothing you started is still up. Leave real users' dashboards alone, since a stopped app stays down until it's reactivated
- **kubectl is strictly read-only on the tenant's EKS cluster.** Never create, modify or delete anything there with kubectl, under any circumstances: no `apply`, `create`, `edit`, `patch`, `delete`, `scale`, `rollout`, `label`, `annotate`, `cordon`, `drain`, `exec` or `cp`. Use only `get`, `describe`, `logs`, `top`, `events` and `auth can-i`. Changes to what runs on the tenant go through Flyte (`flyte deploy`, `update app`, `abort run`) or to the user. The local devbox is exempt: anything goes there
- The bioinformatics CLI tools (gatk, bwa, bwa-mem2, samtools) are not on the dev machine's PATH. They live in `gatk_env`'s image. Every task test runs in its task's image (the `tasks` tier, `uv run --all-extras python cli/docker_task_tests.py`), and test assets that need the tools are generated in that image too (`docker run --platform linux/amd64 <image> ...`). Don't install them locally or ask the user to. Run the tasks tier whenever you add or change a task.
- When adding a task that wraps a new CLI tool, check the `TaskEnvironment` it is decorated against in `src/stargazer/config.py` and confirm the tool is layered onto that env's `flyte.Image` (via `with_apt_packages`, `with_commands`, or the bioconda block in `_BIOCONDA_INSTALL`). If it is missing, add it and notify the user.
- When defining a new `TaskEnvironment` in `src/stargazer/config.py`, always call `.with_uv_project(PROJECT_ROOT / "pyproject.toml")` on its image so the stargazer package and its pip deps end up installed, and set explicit `resources=` (e.g. `flyte.Resources(memory=("2Gi", "6Gi"))`). The devbox node has ~7.75 GiB allocatable and a workflow's pods must fit together in ~6 GiB — see the header of `devbox/setup.sh`.
- **CRITICAL** Do not consider backwards compatibility unless explicitly requested!
- **Keep development minutiae out of user-facing surfaces.** App UI strings/pages, user guides, and the README describe behavior in product terms — a limit, what a control does, what an error means. Do **not** leak implementation detail into them: internal vendor/service names, env vars, workaround mechanisms, ticket/plan references, or "X limit, not ours" rationalizations. (E.g. an upload cap reads "100 MB", not "100 MB — a Pinata limit; larger needs TUS".) That rationale lives in code comments and tickets — and architecture docs under `docs/architecture/` may name internals since they're the technical spec, not a product surface.
- Run `uv run ruff check --fix . && uv run ruff format .` after every set of changes to satisfy the pre-commit. This only holds because the ruff version is pinned in **two** places that must match: `rev:` in `.pre-commit-config.yaml` (pre-commit builds its own isolated env) and the `ruff` pin in `pyproject.toml`'s dev group. Bump them together — when they drifted across 0.14→0.16, ruff's *default* rule set went from 59 rules to 413 and the two gates silently enforced different things. Deliberate rule exceptions live in `[tool.ruff.lint]` in `pyproject.toml`, each with a comment saying why.
- Ruff also enforces the import layers (`TID251`): a module never imports from a layer above its own. Each layer's directory has a `ruff.toml` banning the layers above it; the rules are in `src/stargazer/ruff.toml`. A nested file's ban list replaces its parent's, so a new layer directory lists every ban that applies to it. To see the import graph, `cli/diagrams.sh` draws it into the gitignored `diagrams/`, with its own `diagrams` dependency group (see `cli/README.md`).
- Prefer bounded version ranges (`>=X,<Y`) over open-ended ones for anything whose API you import. Two breakages this project has actually hit came from unbounded pins walking across a major: `ruff` (rule-set change) and `mcp` (1.x→2.0 renamed `FastMCP`/`mcp.server.fastmcp` to `MCPServer`/`mcp.server`).

## Skills and Agents

The agent harness is Claude Code's, kept in the formats other harnesses read too: this file for instructions, `.claude/skills/<name>/SKILL.md` for skills (the shared Agent Skills format), `.claude/agents/` for subagents, `.mcp.json` for the Stargazer MCP server and `.claude/settings.json` for shared settings. A skill's description says when to use it, and its body loads only then. Skills are broad: each applies across the project, to any task, workflow or change. A skill or subagent never holds anything specific to one task, tool, workflow, notebook, asset type or feature: no per-feature recipes or maps, no scripts for one pipeline, no lists of a type's fields or a module's settings, which drift from the code they copy. Specifics for one change live in its ticket, such as its `## Verification recipe`, and its evidence in its PR; a check worth repeating becomes a test in its tier. What the MCP server already serves (the tasks and workflows, their signatures) never becomes a skill, and reference material on what Stargazer builds on lives in the wiki, `.claude/context/`. Several skills are adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack) (MIT).

| Skill | Use it when |
|-------|-------------|
| `tasks-and-workflows` | Adding or changing any task or workflow in `src/stargazer/tasks/` or `src/stargazer/workflows/` |
| `write-tests` | Writing or running tests. The reference for the test tiers, isolation and fixtures |
| `architecture` | Planning a feature as a ticket, or checking whether a change needs a doc update |
| `write-docs` | Writing or editing anything under `docs/`: voice and doc conventions |
| `bug-fix` | A defect is reported. Reproduce on the same surface, find the cause by elimination, fix at the root, verify on the same surface |
| `blast-radius` | A change could break something outside its diff (stored keyvalues, MCP wire format, Flyte images, notebook imports). Proves the one fact it's safe because of by running code |
| `wiki` | Looking up Flyte, marimo or a wrapped tool's parameters; changing code a wiki page points at; adding a source to the wiki |
| `verify-stargazer` | Before declaring a task, workflow, notebook or app change done. How to drive and check a change on each surface: a notebook headless against an isolated asset store, the devbox, the Union tenant as the test account |

| Subagent | Use it for |
|----------|------------|
| `code-reviewer` | A strict, evidence-backed review of a diff or branch before its PR opens, in its own context |

## Docstring Spec References

Every module in `src/` has two conventions in its module-level docstring:

1. The first line is a `###` heading so it renders prominently in the generated API docs.
2. A `spec:` line at the bottom is a markdown link to the relevant architecture doc:

```
spec: [docs/architecture/types.md](../architecture/types.md)
```

The link is relative to `docs/reference/api.md`, where mkdocstrings renders every `src/` module, so it is `../architecture/<doc>.md` however deep the module sits. `runtime/proxy.py` isn't rendered there and links relative to its own file (`../docs/architecture/runtime.md`).

**Rationale:** This serves two purposes:
1. **Diff scanning** — when reviewing recent PRs or commits, an LLM can immediately see which spec doc is affected by any changed module and check whether the docs need updating.
2. **Low-overhead lookup** — when making changes to a specific module, the relevant high-level architecture is one link away without any search.

The `spec:` line is **module-level only** — class and function docstrings do not carry it.

100% docstring coverage is enforced by the `docstr-coverage` pre-commit hook.

## Specs, Tickets and Reference Materials

- **The devbox** - Its setup lives in `devbox/setup.sh`, and each of its steps carries the quirk it works around. Check it first when running on or debugging the devbox, and run it after recreating the container. A devbox quirk that Stargazer's own code works around gets a comment at that code. The devbox tier here assumes the devbox is set up and `FLYTE_IMAGE_REGISTRY=localhost:30000` is exported (never `image.registry` in `.flyte/config.yaml`: Flyte reads that file's when an image is defined, so it would leak into a Union run from the same checkout).
- **`.claude/context/`** - The agent wiki, read on demand from its `index.md`: what Stargazer builds on (Flyte, marimo, the tools tasks wrap), as interlinked pages kept in the Karpathy LLM-wiki pattern, synthesized from the raw sources in `raw/` and pointing into the code. Stargazer's own internals aren't in it: a fact about the code lives in a docstring or comment at the code, where a diff shows it, and a cross-module one in `docs/architecture/`. The `wiki` skill holds its conventions and how to query, ingest and lint it. It's on `main`, and the `planning` branch's worktree sits inside it, so `.claude/context` opened as an Obsidian vault holds the wiki and the ticket board
- **`docs/`** - Project documentation (architecture, guides, reference)
  - **Critical**: Docs must be updated as the project evolves to stay in sync with the current state
  - No code in architecture docs - these are high-level references supported by docstrings in the actual functions
  - Durable docs (`docs/`, the wiki, skills, this file) describe how things are now. Don't log what changed, what's gone or which ticket did it: that history is in commit messages and PR descriptions, and in a durable doc it only adds to every agent's context
  - Guides are the only docs that contain code examples
  - **Every doc must be reachable from the `nav` in `zensical.toml`.** The nav is hand-maintained, so a new `docs/**/*.md` is invisible (built but unlinked) until you add it. Whenever you add, rename, move, or delete a doc, update `nav` to match, then verify nothing is orphaned: every file under `find docs -name '*.md'` must appear in `zensical.toml`'s `nav` (mkdocstrings-target files like `reference/api.md` included). A new architecture/notebook subpackage also needs an `__init__.py` with the `###` heading + `spec:` line, or the docs build fails to collect it.
- **`.claude/context/planning/`** - Tickets, one markdown file per piece of work, on the `planning` branch. That branch is never merged into anything. Its only history in common with `main` is `main`'s first commit, which lets it hold a standing draft PR (#22) so GitHub doesn't offer to open a PR after every ticket push. Leave that PR open and don't treat it as review work. It is checked out exactly once, as a worktree at the main checkout's `.claude/context/planning/` (gitignored on `main`), and every session and the Obsidian board use that one copy, so a ticket edit is visible everywhere as soon as it's saved. From any worktree it's `$MAIN/.claude/context/planning`, with `MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")`. A fresh clone sets it up from the main checkout with `git fetch origin planning && git worktree add .claude/context/planning planning`.
  - **What's a ticket:** each is named after its slug, which is also its branch's slug (`planning/scrna-oom.md` ↔ `fix/scrna-oom`). Known gaps, deferred work and "open issues" are tickets, **not** notes scattered across `docs/`: when you defer something or surface a production gap while working, write a ticket rather than leaving an "Open Issues" section in an architecture doc. A sub-item that will ship in its own PR is its own ticket. An idea that's being weighed but isn't committed to is a ticket with `status: maybe`; like every ticket, it's public. Private drafts go in `.claude/brainstorm/` (below), never here.
  - **Frontmatter:** `title` (plain text, no markdown), `status` (`maybe`, `backlog`, `next`, `doing`, `review` or `done`), `priority` (`high`, `normal` or `low`), `created` (`YYYY-MM-DD`). Add `blocked_by` (a list of slugs) or `pr` only when a ticket needs them. Obsidian rewrites the whole block when a card is dragged, so write it the way Obsidian would: no comments, lists one item per line. The `planning` branch's pre-commit checks this.
  - **Body:** what and why first. A small ticket is a paragraph; a big one carries the full plan, with pieces as checkboxes ticked as the work lands, and the verification evidence. A change verified on a real surface carries its `## Verification recipe` (the `verify-stargazer` skill has the shape), which later changes find and rerun. Tickets are the only place outside `src/` where code snippets are allowed.
  - **Lifecycle:** `maybe` until it's decided the work will happen, then `backlog`; `doing` when you cut the change's worktree; `review` and `pr: <number>` when its PR opens; after it merges, `done` and an `## Outcome` section (what shipped, how it was verified, what's left), in the same step that removes the worktree. In that step, also take the ticket out of every other ticket's `blocked_by` (dropping the key once its list is empty), and move a ticket it was holding back to `next` if it's next in line. Done tickets stay in place.
  - **Sequencing:** `next`, `blocked_by` and `priority` are the order. Take work from `next` first, highest priority first; a `backlog` ticket only when `next` is empty or the user asks for it. A ticket blocked by another waits whole: don't split a piece out of it to start early unless the user asks. When two tickets change the same files, the one that goes second gets `blocked_by` the other, since the merge tree is flat.
  - **Committing:** ticket edits never ride in a code PR. Commit them on `planning` as you make them, naming only your own files, since other sessions share the checkout: `git -C "$MAIN/.claude/context/planning" commit -m "<what changed>" -- <files>`, then `git -C "$MAIN/.claude/context/planning" pull --rebase && git -C "$MAIN/.claude/context/planning" push`.
  - **Referencing:** files on `main` mention a ticket by slug (ticket `internal-address-auth`), never by path, since `main` can't link into another branch.
  - **Board:** `board.base` is a kanban grouped by `status`; open `$MAIN/.claude/context` as an Obsidian vault to see it beside the wiki (the main checkout's copy of it). A ticket links a wiki page as `[[page]]`; a ticket's name never matches a page's, which the wiki lint checks. From a shell, `grep -l '^status: next' "$MAIN"/.claude/context/planning/*.md`.
  - **`archive/`** is frozen history from before tickets: the numbered plans `01`–`27`, and `COMPLETE.md`, the old roadmap's Complete list.
- **`.claude/brainstorm/`** - Unslotted ideas, moonshots, and exploratory design that are not tickets yet. **Gitignored and local only** — nothing here is committed or pushed, so it is the place for drafts that should not become public history.
  - Files are unnumbered and free-form; they don't follow ticket conventions or need to stay in sync with the code
  - Never link to a brainstorm file from anything tracked (`docs/`, tickets, code comments) — the link would dangle for everyone else
  - From a worktree it's `$MAIN/.claude/brainstorm`. Read it for context when asked about future direction, but don't treat it as a spec or a commitment
  - **Promoting** an idea: write a ticket in `.claude/context/planning/` (`maybe` or `backlog`). Copy in what survives rather than moving the brainstorm file, and leave the brainstorm file in place

## Project Structure

### Directory Organization

The project follows this structure:
- `runtime/` - The notebook pod's runtime, never part of the package: `Dockerfile` (the one Stargazer image, built from the repo root), `proxy.py` (baked as the top-level module `sg_proxy`), `launch-notebook.sh`, `start-local.sh` (the image's local entrypoint), the HTML fragments the proxy injects, and `notebook_agent.md` (the terminal agent's `AGENTS.md`)
- `src/stargazer/` - Main package
  - `__init__.py` - Package root, re-exports key symbols
  - `config.py` - Centralized configuration, env var defaults, TaskEnvironment definitions (`gatk_env`, `scrna_env`), logger setup
  - `server.py` - MCP server implementation
  - `marshal.py` - Serialization helpers for MCP transport
  - `registry.py` - Task/workflow registry for MCP discovery
  - `tasks/` - Flyte task definitions, organized by domain subdirectory
    - `gatk/` - GATK tool tasks (haplotype_caller, mark_duplicates, sort_sam, etc.)
    - `general/` - General bioinformatics tasks (bwa, bwa_mem2, samtools)
    - `scrna/` - Single-cell RNA-seq tasks (cluster, normalize, qc_filter, etc.)
  - `workflows/` - Flyte workflow definitions (one module per pipeline)
  - `assets/` - Asset dataclasses (all inherit from `Asset` base class)
  - `utils/` - Utility functions (subprocess, pinata, storage, index, cid, query)
  - `bundles/` - Predefined workflow input bundles (YAML configs)
- `tests/` - Test directory
  - `conftest.py` - Pytest configuration (Flyte init, fixture paths, an isolated store/index/cache per test, the seeded fixture store; `PINATA_JWT` is stripped, and the pinata tier's own conftest sets it)
  - `fixtures/` - Test data organized by domain (`gatk/`, `general/`, `scrna/`), plus `seed.py`, which loads it into a test store
  - `assets/` - Tests for `src/stargazer/assets/` (asset types, `assemble()`)
  - `tasks/` - Task-level tests mirroring `src/stargazer/tasks/` structure
  - `utils/` - Tests for `src/stargazer/utils/` (storage, index, CID, Pinata, query, subprocess)
  - `notebooks/` - Smoke tests that every notebook in `src/stargazer/notebooks/` imports and parses
  - `unit/` - Unit tests for the rest: the notebook proxy (`runtime/`), registry, MCP marshalling, bundles, `Asset` itself
  - `devbox/` - The devbox tier: asset storage across pods, the germline workflow. `pod_tasks.py` holds what runs in their pods
  - `pinata/` - The pinata tier: the Pinata client against the real API
  - `postgres/` - The postgres tier: the index tests against a throwaway Postgres container
  - `dsql/` - The dsql tier: the index tests against the real Aurora DSQL cluster, as its admin
  - Each top-level directory here belongs to exactly one tier (`TIERS` in `conftest.py`); the `write-tests` skill's Test Tiers says how each runs. A bare `uv run --all-extras pytest` is the `unit` tier and runs in pre-commit
- `cli/` - Developer scripts: `docker_task_tests.py` (the tasks tier), `upload_to_pinata.py`, `diagrams.sh`, `wiki_lint.py` (see `cli/README.md`)
- `.github/workflows/` - CI: `release.yml` (a calendar tag publishes the package to PyPI and the image to GHCR) and `docs.yml` (the docs site)
- `docs/` - Project documentation
  - `architecture/` - System design and contracts
  - `guides/` - Step-by-step walkthroughs with code examples
  - `reference/` - API reference (catalog of tasks and types)
- `.claude/` - The agent harness (see Skills and Agents above): `skills/`, `agents/` and `context/` (the wiki, with the `planning` branch's worktree inside it, gitignored, holding the tickets and the Obsidian board) are tracked; `worktrees/`, `brainstorm/` (local-only unslotted ideas and moonshots) and `settings.local.json` are gitignored
- `scratch/` - Gitignored, local-only scratch materials

### Types Directory (`src/stargazer/assets/`)

**Purpose:** Define all input and output dataclasses used across tasks and workflows.

**Guidelines:**
- Create separate modules for different domains (e.g., `reference.py`, `alignment.py`, `variants.py`, `reads.py`, `scrna.py`)
- All types inherit from the `Asset` base class (`asset.py`) which provides `cid`, `path`, `to_keyvalues()`, `from_keyvalues()`, and registry mechanics
- Use descriptive dataclass names (e.g., `Alignment`, `Variants`, `Reference`)
- Group related types in the same module
- Use Python dataclasses with type annotations

### Tasks Directory (`src/stargazer/tasks/`)

**Purpose:** Define individual Flyte tasks that perform specific operations.

**Guidelines:**
- **Modular Organization:** Tasks are organized into domain subdirectories (`gatk/`, `general/`, `scrna/`) with one file per tool (e.g., `gatk/haplotype_caller.py`, `general/bwa.py`)
- **Naming Convention:** Use descriptive, action-oriented names
  - Task files: `{tool}.py` or `{function}.py` within domain subdirectories
  - Task functions: `{action}_{tool}` (e.g., `bwa_mem`, `haplotype_caller`, `sort_sam`)
- **One Task Per Function:** Each task should do one thing well. A task never makes up for a missing input by doing another task's work (indexing, re-running a tool, calling another task): it raises, naming the missing input and the task that produces it. Running one task after another belongs in a workflow
- **Use Structured I/O:** Leverage dataclasses from `assets/` for inputs/outputs
- **Resource Specification:** Define appropriate resource requests (CPU, memory, GPU)

### Workflows Directory (`src/stargazer/workflows/`)

**Purpose:** Compose tasks into end-to-end workflows.

**Guidelines:**
- **Modular Organization:** Separate workflows by analysis type or pipeline (e.g., `germline_variant_calling.py`, `somatic_variant_calling.py`)
- **Naming Convention:** Use descriptive, pipeline-oriented names
  - Workflow files: `{analysis_type}.py` or `{pipeline_name}.py`
  - Workflow functions: `{pipeline_description}` (e.g., `germline_variant_calling_pipeline`)
- **Clear Composition:** Show task dependencies clearly
- **Use Structured I/O:** Leverage dataclasses for workflow inputs/outputs

### Core Concepts

- Main SDK import: `import flyte`
- Task environments are defined in `config.py`: `gatk_env` (GATK/BWA/samtools) and `scrna_env` (scanpy-based scRNA)
- Decorate tasks with `@gatk_env.task` or `@scrna_env.task` (not a generic `pb_env`)
- Async tasks are preferred for I/O operations
- In v2, there is no separate `@workflow` decorator - workflows are tasks that call other tasks
- Use `asyncio.gather` for parallel execution
- All types inherit from `Asset` base class, which provides `cid`/`path` fields, `to_keyvalues()`/`from_keyvalues()` serialization, and an auto-registry via `_asset_key`

## Style and Conventions

- **Paths:** Use `pathlib.Path` for all filesystem operations (e.g., `joinpath`). Use `resolve()` for absolute paths. Only convert to `str` immediately before a subprocess call.
- **Formatting:** Use `ruff` for formatting and correctness checking
- **Imports:** Use the `stargazer` package name, not relative imports across packages. Module level imports should be at the top of the file!!
- **Documentation:** Include docstrings explaining purpose and behavior
- **Comments:** A comment says what the code can't: why it's done this way, a constraint or invariant it upholds, the external quirk it works around, a non-obvious unit or shape. Don't write comments that restate the next line (`# Assemble the reference` above `refs = await assemble(...)`), narrate control flow (`# Unwrap single outputs` above `if len(named) == 1:`), label a block whose names already say what it does (`# GenomicsDBImport` above `import_cmd = ["gatk", "GenomicsDBImport", ...]`), or group entries in a list that ruff will re-sort. If the code needs a comment to be understood, try a better name first. When you touch code, delete the superfluous comments around it.
- **Resource Awareness:** Specify appropriate resource requests for bioinformatics workloads
