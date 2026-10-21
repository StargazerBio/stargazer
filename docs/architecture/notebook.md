# Notebooks

The marimo notebook is Stargazer's primary user surface. Researchers often think in analyses — load data, run a pipeline, look at a plot — and the notebook gives them that experience while everything underneath stays reproducible: the tasks a notebook calls are the same typed, versioned, image-pinned SDK code that runs in production, and the execution context (local vs remote cluster) is a config concern, not a code change.

The SDK (`src/stargazer/` — assets, tasks, workflows) is a first-class surface in its own right: importing tasks and authoring workflows directly in an IDE is a perfectly legitimate way to work, and nothing about it is reserved for maintainers. Notebooks are simply the more approachable entry point — most users meet the SDK through them first. The two layers exist for each other:

- **The SDK exists so notebooks are trustworthy.** A notebook cell that calls `bwa_mem` or the scRNA pipeline is calling tested, resource-specified, container-pinned code — not a copy-pasted shell command.
- **Notebooks exist so the SDK gets used and grown.** They are where new analyses are prototyped, where new tasks are first written, and where finished work is published. Every promotion path below starts in a notebook and ends in the SDK or the repo.

This doc covers what notebooks *are* — the taxonomy, who uses them, and how work moves between notebooks and the SDK. The hosting machinery (dashboard, workspace store, pods, sign-in) is covered in [App](app.md).

## Execution Context

Where *tasks* run. Notebooks call `flyte.init_from_config()` at startup, and `.flyte/config.yaml` names the cluster that remote runs go to. Whether a run goes there or stays in the notebook's own process is decided where it's started, never in the task: the same task or workflow runs either way, unchanged. That's what lets one notebook span the whole arc: run on the notebook's own machine it's an exploratory scratchpad, and run on a cluster it's a production workflow management interface, launching, parameterizing, and tracking pipelines. The Execution tutorial makes the two underlying calls side by side.

For whoever runs a notebook, the choice is a control. `stargazer.notebooks.ui` provides `run_location()`, a two-way switch between *On this machine* (the default) and *On the cluster*, and `dispatch()`, which runs a task or workflow wherever the switch is set, waits for it, and returns its result. *On the cluster* always asks for a remote run, so with no cluster configured it fails instead of quietly running locally. The Execution tutorial ends by introducing it.

A cluster can only run tasks its pods can import: the SDK's, and those a notebook declares as reusable top-level functions (`@app.function`, the way the Execution tutorial imports the Workflows tutorial's workflow). A task defined inside a regular cell runs only on the notebook's own machine.

## Notebook Types

The dashboard renders two sections, and the repo holds a third kind of notebook:

| Type | Where | Source of truth | Purpose |
|------|-------|-----------------|---------|
| **Tutorials** | `src/stargazer/notebooks/tutorials/` | Image-baked (upstream repo) | Learn the building blocks — a reading sequence: Assets → Tasks → Workflows → Execution |
| **Workspace** | — | User's workspace store | The user's own notebooks — authored from scratch or a template, persisted across sessions |
| **Repo notebooks** | `notebooks/` at the repo root | The repo, on GitHub | Complete analyses, such as the scRNA-seq pipeline and reimplementations of papers, run against your own data |

Tutorials ship in the image and work for everyone. A user's Workspace is one folder, saved whole in the [workspace store](app.md#core-concepts), keyed by their account, with no setup: the notebooks side by side at the top, so they can import each other, plus whatever data or helper files the user keeps beside them. The tile registry for image-shipped notebooks is `app/notebooks.py`; the user's own tiles are listed from the store at render time.

Repo notebooks aren't on the dashboard. They live where GitHub shows them and pull requests review them, they aren't assets, and they aren't packaged or baked into the notebook image, so a change to one needs no image release. They run from a checkout. A tutorial teaches a concept and is read once; a repo notebook is a complete analysis meant to be run again against new data.

## User Archetypes

Notebook types map onto a progression. Each rung uses everything below it:

1. **Analyst** — runs the repo's notebooks against their own data, with the Tutorials as the reference for the building blocks. Parameters and uploads happen in the notebook UI.
2. **Author** — writes their own notebooks. Their work persists across sessions, and any notebook can be downloaded and contributed upstream.
3. **Contributor** — promotes notebook-grown code into the SDK: tasks into `src/stargazer/tasks/`, proven pipelines into `notebooks/`. Works against the repo natively — see [Contributing](../guides/contributing.md).

Orthogonal to the ladder are **SDK-native users** (authoring workflows in an IDE by importing `stargazer` tasks directly), **agent users** (driving the MCP server from Claude Code, Cursor, etc.), and **maintainers** (curating the SDK, reviewing promotions, publishing images). The same person frequently occupies several rungs in one session — the point of the design is that moving up a rung never requires abandoning the notebook.

## Promotion Paths

Work flows from experimentation toward the SDK and the public repo along two paths, both starting in a Workspace notebook. Promotion happens in the repo, not on the dashboard:

```mermaid
flowchart LR
    W[Workspace notebook] -->|promote task| T[src/stargazer/tasks/]
    W -->|graduate pipeline| P[notebooks/]
    T -->|PR| U[(upstream Stargazer)]
    P -->|PR| U
```

### Task promotion — notebook cell → SDK task

Researchers define tasks directly in notebook cells using proper Flyte conventions — `@gatk_env.task`, asset types, async signatures. These are real tasks that run against real data in the notebook.

1. **Author** in a notebook cell — proper decorators, structured I/O, async patterns. The task works in the notebook as-is.
2. **Promote** — mechanical extraction: strip the cell wrapper, move the function into the right `src/stargazer/tasks/` subdirectory, generate a skeleton test.
3. **Review** — a code-review agent picks up the PR and suggests changes to fit project conventions (docstrings, naming, test coverage). Convention enforcement happens at review time, not authoring time.

Researchers write a working task; promotion does the mechanical extraction; PR review adds the polish. Once a promoted task needs refinement beyond what review suggests, work continues natively against the repo like any other SDK change — see [Contributing](../guides/contributing.md).

### Workflow graduation — workspace notebook → repo notebook

A workspace notebook that proves out a *reusable* pipeline — one others should run against new data — graduates into the repo's `notebooks/` folder. Graduation is the composite path: first its cell-defined tasks go through task promotion (above), so the heavy lifting lives in the tested SDK; then the notebook itself — now a thin, parameterized UI over SDK calls — is PR'd into `notebooks/`. It gets no dashboard tile and needs no image release: once merged, it's on GitHub for everyone. The scRNA-seq notebook is the template for what a graduated workflow looks like.

## The SDK Loop

Promotion is half a cycle; the other half is the SDK flowing back into notebooks:

1. Prototype a task in a Workspace notebook (it runs for real, immediately).
2. Promote it into `src/stargazer/tasks/`; it gets tests, review, and a docstring.
3. The next image release bakes it into every notebook environment.
4. Every notebook — tutorials, the repo's notebooks, anyone's workspace — can now import it, and new prototypes compose it.

This loop is why the boundary and packaging rules below exist: they are what makes step 3 safe.

### Boundary rule

**The SDK never imports notebooks.** The dependency graph between the layers is strictly one-directional:

```mermaid
flowchart TD
    S[stargazer.tasks / workflows / assets / utils] -->|import only| N[notebooks/*.py]
```

Notebooks are free to experiment, prototype, and visualize — but they are never a dependency of production code, so notebook changes cannot break tasks or workflows.

Notebook-to-notebook reuse *is* allowed: marimo notebooks can export importable definitions via `app.setup` + `@app.function`, and the Execution tutorial imports the Workflows tutorial's workflow this way rather than duplicating it. The invariant is about the SDK layer, not about notebooks sharing code among themselves.

### Packaging boundary

In production, each notebook's sandbox installs the SDK from the image's own source tree at `/stargazer` (the `[tool.uv.sources]` entry in its PEP 723 header), fixed when the image was built. This means:

- **Package tasks** in `src/stargazer/tasks/` are available in every production notebook automatically.
- **Notebook-defined tasks** run in the notebook that defines them, but are not importable elsewhere until promoted into the package.

This is a feature — it prevents untested code from silently ending up in production. Locally a notebook imports your checkout, so contributors see SDK changes as they make them. It also means saved notebooks can't change execution: the workspace store carries notebook *sources*; the SDK they import always comes from the image.

## Notebook Environment

A notebook's environment has two halves, and each has its own home:

- **Python packages** go in the notebook's PEP 723 header. They install into the notebook's own environment when it starts, with no image to rebuild, so this is where iteration stays fast.
- **System tools** (apt packages, bioconda tools, command-line binaries) go in the image the notebook runs on. A notebook declares that image in its setup block as `main_img`: a `flyte.Image` built on `notebook_base`, the standard notebook image, using any of the SDK's `Image` methods that don't copy in local files. It's the same API a production `TaskEnvironment` uses, so an environment proven in a notebook carries over to a task as-is. Notebooks created from the template start with one to edit.

At launch the declared image is built if it isn't already, and the notebook is served on it. An unchanged image is reused, so only the first launch after a change waits for a build. A change takes effect the next time the notebook launches. If the image can't be built, the launch fails with the reason instead of opening the notebook without its tools.

The `main_img` line is evaluated on its own, so it can use `flyte` and `notebook_base` but not other names from the setup block. Building needs the hosted deployment. Tutorials run on the standard image.

## Notebook Modes

How the *notebook UI* is served — orthogonal to execution context. A notebook in either mode can dispatch tasks locally or remotely.

| Mode | Behavior | Used for |
|------|----------|----------|
| **Edit** | Full marimo editing UI | Tutorials, Workspace authoring |
| **Run** | Read-only app view (`--include-code`) | Shareable views of any notebook |

A notebook runs in one mode at a time — see [App → Core Concepts](app.md#core-concepts).

## Adding Notebooks

- **Workspace notebooks** are created from the dashboard (the blank or basic seed in `app/seeds/`) and live in the user's workspace store — no repo change involved.
- **Tutorials** ship in the image: add the `.py` file (standard marimo format, importing only `stargazer` public APIs) under `src/stargazer/notebooks/tutorials/`, register a tile in the `NOTEBOOKS` tuple in `app/notebooks.py`, and it lands when onboarding next builds the `notebook-app` image (`stargazer-users upgrade`).
- **Repo notebooks** are a pull request adding the `.py` file to `notebooks/`. Nothing else registers them.

## In-Notebook AI

**Claude Code rides along in the hosted notebook** — the proxy injects a dropdown terminal overlay (Ctrl+`) into every notebook page with the Claude Code CLI on PATH, for agentic work against the notebook's files and environment. The terminal starts in `/workspace`, and the image bakes one condensed context file, `app/notebook_agent.md`, there as `AGENTS.md`, so every session starts knowing what the pod is (what `/workspace` saves, what's lost when the pod stops), marimo's notebook conventions, Stargazer's task, asset and workflow patterns, and how a run goes local or to the cluster. Until a user edits it, it isn't saved with their workspace, so each launch gets the image's current copy. Once they edit it, their copy is saved and loaded like any of their files. The `stargazer` image seeds the same file into `/workspace` with its notebooks.

The stargazer MCP server serves agent users through external coding tools (Claude Code, Cursor, etc.), exposing `list_tasks`, `run_task`, `query_files`, and the rest of the catalog.
