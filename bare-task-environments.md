---
title: bare-task-environments
status: review
priority: normal
created: 2026-11-10
pr: 149
blocked_by:
  - project-pod-env-vars
---

A task environment in Stargazer should read like one from the Flyte docs. Decided 2026-11-10, in place of the factories of ticket `task-environment-factory` (PR 147):

- **Variables** come from the project's settings (ticket `project-pod-env-vars`), so no environment passes `env_vars` for Stargazer's sake.
- **Secrets** stay explicit: `secrets=STARGAZER_SECRETS`, Flyte's own argument.
- **The image** keeps its helper: `image=task_image(__file__)` or `notebook_image(__file__, name)`.
- Leaving secrets or the image off is fine for a task that doesn't use Stargazer's storage or start child tasks. A task that does, and is missing what it needs, fails with an error that names what's missing and the argument that provides it.

## Current State

- `tasks/gatk/env.py`, `tasks/scrna/env.py`, `notebooks/templates/basic.py`, `notebooks/tutorials/tasks.py` and `tests/devbox/pod_tasks.py` pass `env_vars=STARGAZER_ENV_VARS`.
- The silent case: `stargazer.config` defaults `STARGAZER_STORE_ROOT` and `STARGAZER_INDEX_URL` to `~/.stargazer/`, so a cluster pod without them stores to its own disk and the next pod finds nothing. Read from the code, not reproduced.
- Already loud: `PinataClient` raises when `PINATA_JWT` is unset (`utils/pinata.py:178`). A pod with no API key can't start a child task (measured on the tenant 2026-10-22), but the error is Union's, not ours.
- An image left off a task defined in a notebook fails at import on the cluster, since the pod imports the notebook's module and Flyte's default image has neither marimo nor the SDK (inferred). That is Flyte's error and loud enough; the guide should say it.

## Plan

- [x] Reproduce the silent case first, on the devbox: a bare-environment task stores an asset, a second task can't assemble it. This is the before for the checks below. Devbox run `rqqv7p89b2sgrh7ckthl`: the store succeeded on the pod's disk.
- [x] Loud storage: a task running on a cluster with no explicit `STARGAZER_STORE_ROOT` or `STARGAZER_INDEX_URL` raises on first use of the store or index, naming the variables and where they come from (the project's settings; `env_vars=` on the devbox if `project-pod-env-vars` found it needs them). How a pod knows it's on a cluster is the open design point: Flyte's task context, not a variable of ours. Local runs keep the `~/.stargazer/` defaults. Shipped as `stargazer.config.require_cluster_storage()`, called by `get_client()`: `flyte.ctx().is_in_cluster()`, and a variable still equal to its local default counts as missing.
- [x] Loud key: a pod about to start a child task with no `_UNION_EAGER_API_KEY` raises naming `secrets=STARGAZER_SECRETS`. Only if it can be checked where Stargazer already has a hand in the call; if not, leave Union's error and document it. It can't: a task's child launch is Flyte's alone. Documented in the guide.
- [x] Drop `env_vars=STARGAZER_ENV_VARS` from the two `env.py` files, the template and the tutorial, once `project-pod-env-vars` has shipped and run for the tenant's projects. Whether `STARGAZER_ENV_VARS` stays for the devbox depends on that ticket's first piece. The infra repo imports it, so check before removing. Dropped from the template and the tutorial only. The devbox doesn't apply a project's variables, so the two `env.py` files keep it and `STARGAZER_ENV_VARS` stays. The PR merges after infra's has shipped and onboarding has re-run.
- [x] Docs: `docs/guides/where-your-code-runs.md` shows the bare environment and says what leaving secrets or the image off means; `docs/architecture/configuration.md`; `AGENTS.md`'s new-`TaskEnvironment` rule; the wiki's task-environments page.

## Verification recipe

- Unit tier for the raising paths, each test seen failing first.
- Devbox: the reproduction above now raises with the new message instead of losing the asset.
- Tenant, as the test account: the template notebook's task with no `env_vars`, "On the cluster", stores an output the next cell's `assemble()` finds; the same task without `secrets=` that starts a child fails with the named error.

Run 2026-11-10: devbox `test_a_pod_given_no_store_refuses_to_store` fails before (`rqqv7p89b2sgrh7ckthl` succeeded) and passes after (`rmm76bckg6psglnd7crh` raises the named error). Tenant, from a checkout in `u-pryce`: a bare environment stores in one pod (`u9rm87fd5vkb9cpgcjtc`) and assembles in the next (`usltp9xzdd7xfndfbt6f`). The template notebook through the dashboard, and the missing-`secrets=` child launch, aren't driven: they need the branch in a notebook image.

Related: [[board]], [[project-pod-env-vars]], [[task-environment-factory]], [[flyte-task-environments]].
