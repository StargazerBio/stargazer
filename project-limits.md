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

Reworked after review ("a re-implementation of existing features"): the limits use Union's own two controls, and nothing in the dashboard.

- [x] Per-task caps: the project's `task_resource.max.cpu`, `.memory`, `.gpu` settings, merged with the project's other overrides (a settings update replaces the whole set)
- [x] At once: an org-scoped Union queue per project (Union refuses project-scoped queues), set as its `run.default_queue`, holding `LIMIT_RUNS` runs and `LIMIT_ACTIONS` actions and capping the totals its running actions request (`max_resources` cpu and memory; `max_accelerators` `nvidia_gpu` when GPUs are allowed), `greedy_capacity`
- [x] `onboard`, `upgrade` and `resume` ensure the limits; re-running is a no-op when they're right
- [x] Verified on the tenant as the test account (infra PR 38 has the evidence)
- [ ] Once this merges: `./stargazer-users upgrade` with the admin's AWS session, to give every existing project its limits (PR 35, the terms, merged first); it waits on [[retire-stargazer-login-project]], since `upgrade` deploys the login app first

## What the limits don't stop

Measured on `u-pryce`, 2026-11-17: a run that names another queue (`queue="default"`) skips the project's queue, and apps, notebook pods included, aren't capped at all. The per-task caps hold however a run starts. The project key can't lift any of them: settings edits (`ACTION_ADMINISTER_PROJECT`) and queue edits are refused, though Union's settings doc says Contributor may edit settings. A hard cap on runs and apps per project would need Union (a namespace ResourceQuota, or project-scoped queues a run can't leave).

## Verification recipe

As an org admin (`FLYTE_API_KEY` from `~/.flyte/stargazer-upgrade.env`), in the infra worktree, against `u-pryce`:

1. Set small limits with `ensure_project_limits("u-pryce")` after setting `app.config.LIMIT_*` (e.g. per task 2 CPU / 4Gi, total 3 CPU, 4 runs), then read back `Queue.get("u-pryce")` and `Settings.get_settings_for_edit(project="u-pryce", domain="development").local_overrides()`. A second call should log no writes.
2. Per-task cap: run a task asking for 3 CPU / 6Gi on an SDK-built image (`flyte.Image.from_debian_base()`) that returns `/sys/fs/cgroup/cpu.max` and `memory.max`; expect `200000 100000` and `4294967296`. The release notebook image can't run tasks: a task pod there starts the notebook server instead.
3. Total cap: wait a minute after setting it, submit two such runs sleeping 90 s, and poll `Queue.details("u-pryce")`. Expect `in_flight_resources` cpu `2000m` of `3000m` and the second run QUEUED until the first finishes.
4. Put the limits back to `tenant.env`'s, and check no runs are live.

Related: [[board]], [[project-costs-daily]], [[retire-stargazer-login-project]].
