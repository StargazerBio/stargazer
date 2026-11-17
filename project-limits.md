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

Reworked twice after review: first onto Union's own controls, then down to the queue alone, with abuse handled by hand rather than in code.

- [x] One org-scoped Union queue per project (Union refuses project-scoped queues), set as its `run.default_queue`. It holds runs (`LIMIT_RUNS`) and actions (`LIMIT_ACTIONS`) at once, and the totals its running actions request: CPU and memory (`max_resources`), and NVIDIA GPUs (`max_accelerators` `nvidia_gpu`, 1 by default; a limit of 0 is refused, since a queue can't cap at 0). `greedy_capacity`
- [x] No per-task cap, so a user chooses between many small tasks and a few big ones
- [x] `flyteplugins-union` 0.16, the first whose class-wide GPU cap the server accepts
- [x] `onboard`, `upgrade` and `resume` ensure the limits; re-running is a no-op when they're right
- [x] Verified on the tenant as the test account (infra PR 38 has the evidence)
- [ ] Once this merges: `./stargazer-users upgrade` with the admin's AWS session, to give every existing project its limits (PR 35, the terms, merged first); it waits on [[retire-stargazer-login-project]], since `upgrade` deploys the login app first

## Not held by the queue

Measured on `u-pryce`, 2026-11-17: a run that names another queue (`queue="default"`) skips the project's queue, and apps, notebook pods included, don't go through queues. Both are handled by hand if they're abused. The project key can't change its queue or settings (`ACTION_ADMINISTER_PROJECT`, `ACTION_MANAGE_QUEUE`). Which GPU types exist is the tenant's node pools, Union's: today `awsg52xlarge` (one A10G each) beside the CPU pool `awsr7i2xlarge`; a queue can cap a type's count but not forbid one.

## Verification recipe

As an org admin (`FLYTE_API_KEY` from `~/.flyte/stargazer-upgrade.env`), in the infra worktree, against `u-pryce`:

1. Set small limits on `app.config.LIMIT_*` (e.g. 4 runs, 3 CPU total) and call `ensure_project_limits("u-pryce")`; read back `Queue.get("u-pryce")` and the project's `local_overrides()`. A second call should log no writes.
2. Total cap: wait a minute, submit two tasks of 2 CPU each on an SDK-built image (`flyte.Image.from_debian_base()`) sleeping 90 s, and poll `Queue.details("u-pryce")`: expect `in_flight_resources` cpu `2000m` of `3000m` and the second QUEUED until the first finishes. The release notebook image can't run tasks: a task pod there starts the notebook server instead.
3. No per-task cap: a task asking for 6 CPU / 8Gi reports `cpu.max=600000 100000` from its cgroup.
4. Put the limits back to `tenant.env`'s and check no runs are live.

Related: [[board]], [[project-costs-daily]], [[retire-stargazer-login-project]].
