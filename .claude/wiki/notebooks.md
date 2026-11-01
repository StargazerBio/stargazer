---
sources:
  - docs/architecture/notebook.md
  - src/stargazer/notebooks/__init__.py
  - src/stargazer/notebooks/ui.py
  - runtime/notebook_agent.md
  - "[[marimo-inlining-dependencies]]"
---

# Notebooks

How notebooks are dispatched, packaged and launched, beneath `docs/architecture/notebook.md`. Read it before changing any of the three.

## Dispatch

- **A run's code ships from the task's own module directory.** `dispatch()` (in `src/stargazer/notebooks/ui.py`) sends a run's code from the directory the task's module was imported from, so a notebook's own tasks travel with it wherever it lives, a user workspace included.
- **On the cluster means remote, always.** `run_location()`'s *On the cluster* always requests a remote run: with no cluster configured it fails rather than quietly running locally. See [[flyte#Running tasks]] for the local and remote run modes.
- **A notebook-declared task's image must carry its module's imports.** The tutorials' `tutorial_env` carries stargazer and marimo. See [[images]].

## Packaging

- **The SDK comes from the image, not the store.** In production each notebook's sandbox installs the SDK from the image's tree at `/stargazer`, through the `[tool.uv.sources]` entry in its PEP 723 header, fixed at image build. The workspace store carries notebook *sources* only. The mechanism is marimo's sandbox: [[marimo-sandbox]].
- **Notebook-defined tasks stay local until promoted.** They aren't importable elsewhere until promoted into the package, which keeps untested code out of production.

## main_env

`main_env` is a `flyte.app.AppEnvironment` cloned from `notebook_env` (see [[flyte-apps]]), whose image is built on `notebook_base`.

- **The notebook declares the pod; the dashboard runs it.** The pod runs on what `main_env` declares: image, resources, environment variables. The dashboard sets the rest: the pod's name, how it starts, its address and who can reach it, and the env vars belonging to whoever launches it, which win over the notebook's. A resource the notebook omits gets the default (`NOTEBOOK_RESOURCES`), disk included.
- **The tile's text is plain strings.** The dashboard reads `main_name` and `main_description` without running the notebook.
- **The `main_env` line is evaluated on its own.** It can use `flyte`, `notebook_base` and `notebook_env`, not other setup-block names. Building an image needs the hosted deployment; sizing the pod doesn't.
- **`STARGAZER_NOTEBOOK_IMAGE` is the pod's own image**, which `notebook_base` builds a declared image on. See [[images#The notebook image]].
- **A notebook opened inside a running pod** (through marimo's file explorer) runs in the environment of the notebook the pod was launched for, not its own `main_env`.

## Workspace and copies

- **Copy to workspace takes the source's name**, and is refused if a notebook of that name exists. The mechanics are on the dashboard side, in the infra repo.
- **The pod's `/workspace/AGENTS.md` is baked from `runtime/notebook_agent.md`.** Until a user edits it, it isn't saved with their workspace, so each launch gets the image's current copy; once edited, their copy is stored and hydrated over it. See [[runtime]].

## Related

- [[runtime]]: the pod a notebook runs in
- [[marimo-sandbox]]: how a notebook's PEP 723 header becomes its venv
