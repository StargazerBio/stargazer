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

- **Every notebook pod is an app.** `notebook_env` is an `AppEnvironment`, and a notebook's `main_env` clones it. The dashboard deploys it at launch, setting the name, the launch command, the port, access and scaling ([[notebooks#main_env]]). On the cluster it runs under Flyte's `fserve` ([[runtime#Cross-cutting facts]]).
- **The dashboard's own apps are in the infra repo**, as is every other hosted service's `AppEnvironment`.
- **An idle app holds its pod and node** until its `scaledown_after` passes, so an app started for a test is deactivated when the test is done (the teardown rule in `AGENTS.md`).
