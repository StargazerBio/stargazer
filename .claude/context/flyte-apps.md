---
sources:
  - "[[flyte-sdk-examples]]"
  - src/stargazer/notebooks/__init__.py
  - runtime/launch-notebook.sh
---

# Flyte apps

Long-running services on Flyte: an app holds a pod and serves a port, where a task runs to completion. Source: [[flyte-sdk-examples#16. Apps & Services]].

- **`flyte.app.AppEnvironment`** takes a `name`, `image`, `command` and `resources`, like a task environment with a server command.
- **`flyte.app.extras.FastAPIAppEnvironment`** serves a FastAPI `app` object; `requires_auth=False` opens it to callers without a login.
- **`flyte.deploy(app_env)`** deploys it; the CLI manages it afterwards (`flyte get app`, `flyte update app <name> --deactivate`).
- **A task can call an app** whose environment it lists in `depends_on`, at `app_env.endpoint` ([[flyte-task-environments#Between environments]]).

## In Stargazer

- **Every notebook pod is an app**: `notebook_env` and `main_env` in `src/stargazer/notebooks/__init__.py`, launched under `fserve` as `runtime/launch-notebook.sh` describes.
- **The dashboard's apps, and every other hosted service's, are in the infra repo.**
- **Tearing down a test's apps** is a rule in `AGENTS.md`.
