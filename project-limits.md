---
title: project-limits
status: review
priority: high
created: 2026-11-17
pr: 38
blocked_by:
  - retire-stargazer-login-project
---

The free tier's guardrail on spend. Cost reports ([[project-costs-daily]]) arrive a day late, so a runaway workload could run for up to 24 hours before anyone sees it. Infra PR 35 (`feat/eula`) puts a terms-of-use gate on every dashboard whose terms say the workspace is free during the alpha within its project's limits on CPU, memory, GPUs and concurrent runs; this sets those limits. PR 35 merged first, so they should roll out soon after.

Infra's onboarding (`stargazer-users`, `stargazer_users/`) sets the limits on every user project, from `STARGAZER_LIMIT_*` in `tenant.env`, and `upgrade` brings existing projects to them. Branch `feat/project-limits` in infra.

## Plan

- [x] Per-task caps: the project's `task_resource.max.cpu`, `.memory`, `.gpu` settings, merged with the project's other overrides (a settings update replaces the whole set)
- [x] Concurrent runs: an org-scoped Union queue per project (Union refuses project-scoped queues), holding `LIMIT_RUNS` runs and `LIMIT_ACTIONS` actions, set as the project's `run.default_queue`
- [x] Notebook pods (apps, which Union's settings don't cap): the dashboard clamps each pod's resources to the per-pod caps and refuses a launch past `LIMIT_NOTEBOOKS` running notebooks
- [x] `onboard`, `upgrade` and `resume` ensure the limits; re-running is a no-op when they're right
- [x] Verified on the tenant as the test account (infra PR 38 has the evidence)
- [ ] Once this merges: `./stargazer-users upgrade` with the admin's AWS session, to give every existing project its limits (PR 35, the terms, merged first); it waits on [[retire-stargazer-login-project]], since `upgrade` deploys the login app first

## What the limits don't stop

Measured on `u-pryce`, 2026-11-17: a run that names another queue (`queue="default"`) skips the project's queue, and an app served from the user's own code skips the notebook clamp and cap. The per-task caps hold however a run starts. The project key can't lift any of them: settings edits (`ACTION_ADMINISTER_PROJECT`) and queue edits are refused. A hard cap on concurrent runs and apps per project would need Union (a namespace ResourceQuota, or project-scoped queues a run can't leave).

## Verification recipe

As an org admin (`FLYTE_API_KEY` from `~/.flyte/stargazer-upgrade.env`), in the infra worktree, against `u-pryce`:

1. Set small limits with `ensure_project_limits("u-pryce")` (e.g. `STARGAZER_LIMIT_CPU=2`, `_MEMORY=4Gi`, `_RUNS=1`), then read back `Settings.get_settings_for_edit(project="u-pryce", domain="development").local_overrides()` and `Queue.get("u-pryce")`.
2. Clamp: run a task asking for 3 CPU / 6Gi on an SDK-built image (`flyte.Image.from_debian_base()`) that returns `/sys/fs/cgroup/cpu.max` and `memory.max`; expect `200000 100000` and `4294967296`. The release notebook image can't run tasks: a task pod there starts the notebook server instead.
3. Queue: submit three `sleep 120` runs and poll `Run.get(name).phase`. Expect one RUNNING and the rest QUEUED, going one at a time.
4. Notebooks: onboard with `STARGAZER_LIMIT_NOTEBOOKS=1`, open the dashboard as the test account, click Edit on one notebook and then Run on another. Expect the second refused with 422. Read `App.get("nb-<slug>-<mode>").pb2.spec.container.resources` for the clamp.
5. Bring the limits back to `tenant.env`'s with `upgrade_user`, and stop the notebooks and the test account's dashboard.

Related: [[board]], [[project-costs-daily]], [[retire-stargazer-login-project]].
