# Notebooks — Internals (agent reference)

The companion to the human-facing [notebooks doc](../../../docs/architecture/notebook.md). Read it before changing how notebooks are dispatched, packaged or launched.

## Dispatch

- `dispatch()` sends a run's code from the directory the task's module was imported from, so a notebook's own tasks travel with it wherever it lives, a user workspace included.
- `run_location()`'s *On the cluster* always requests a remote run: with no cluster configured it fails rather than quietly running locally.
- A notebook-declared task's environment image must carry what the task's module imports (the tutorials' `tutorial_env` carries stargazer and marimo).

## Packaging

- In production each notebook's sandbox installs the SDK from the image's tree at `/stargazer` via the `[tool.uv.sources]` entry in its PEP 723 header, fixed at image build. The workspace store carries notebook *sources* only.
- Notebook-defined tasks aren't importable elsewhere until promoted into the package, which keeps untested code out of production.

## `main_env`

- The pod runs on what `main_env` declares: image, resources, environment variables. The dashboard sets the rest: the pod's name, how it starts, its address and who can reach it, and the env vars belonging to whoever launches it, which win over the notebook's. A resource the notebook omits gets the default, disk included.
- The dashboard reads `main_name` / `main_description` without running the notebook, hence plain strings.
- The `main_env` line is evaluated on its own: it can use `flyte`, `notebook_base` and `notebook_env`, not other setup-block names. Building an image needs the hosted deployment; sizing the pod doesn't.
- `STARGAZER_NOTEBOOK_IMAGE` is the pod's own image, which `notebook_base` builds a declared image on.
- A notebook opened inside a running pod (via marimo's file explorer) runs in the environment of the notebook the pod was launched for, not its own `main_env`.

## Workspace and copies

- Copy to workspace takes the source's name; if a notebook of that name exists the copy is refused. The mechanics are on the dashboard side, in the infra repo.
- The pod's `/workspace/AGENTS.md` is baked from `runtime/notebook_agent.md`. Until a user edits it, it isn't saved with their workspace, so each launch gets the image's current copy; once edited, their copy is stored and hydrated over it.
