---
title: project-limits
status: done
priority: high
created: 2026-11-17
pr: 38
---

The free tier's guardrail on spend. Cost reports ([[project-costs-daily]]) arrive a day late, so a runaway workload could run for up to 24 hours before anyone sees it. Infra PR 35 (`feat/eula`) puts a terms-of-use gate on every dashboard whose terms say the workspace is free during the alpha within its project's limits on CPU, memory, GPUs and concurrent runs; this sets those limits. PR 35 merged first, so they should roll out soon after.

Infra's onboarding (`stargazer-users`, `stargazer_users/`) sets the limits on every user project, from `STARGAZER_LIMIT_*` in `tenant.env`, and `upgrade` brings existing projects to them. Branch `feat/project-limits` in infra.

## Plan

Reworked twice after review: first onto Union's own controls, then down to the queue alone, with abuse handled by hand rather than in code.

- [x] One org-scoped Union queue per project (Union refuses project-scoped queues), set as its `run.default_queue`. It holds runs (`LIMIT_RUNS`) and actions (`LIMIT_ACTIONS`) at once, and the totals its running actions request: CPU and memory (`max_resources`), and GPUs of one allowed type (`max_accelerators` `nvidia_gpu/<type>`, 1 `nvidia-a10g` by default; a limit of 0 is refused, since a queue can't cap at 0). `greedy_capacity`
- [x] No per-task cap, so a user chooses between many small tasks and a few big ones
- [x] GPUs capped by type: a queue counts a typed request only against its own type's cap and leaves unnamed types uncapped, so the project's `task_resource.default_accelerator` gives untyped requests the allowed type, and the admin keeps the GPU node pools to that type. Measured: two `A10G:1` and two untyped `gpu=1` tasks ran one at a time, each charged `nvidia_gpu/nvidia-a10g`
- [x] Notebooks held to the same CPU, memory and GPU totals by the dashboard, apart from tasks, since queues don't hold apps: every launch sums the requests of the owner's open `nb-*` apps (desired state started or active) plus the new pod's, and refuses past a total (`app/notebook_budget.py`). Several small notebooks or one large GPU one. Measured against real app specs on u-pryce; a refusal through the dashboard page isn't verified yet (the test account's terms gate)
- [x] `flyteplugins-union` 0.16, the first whose class-wide GPU cap the server accepts
- [x] `onboard`, `upgrade` and `resume` ensure the limits; re-running is a no-op when they're right
- [x] Verified on the tenant as the test account (infra PR 38 has the evidence)
- [ ] Once this merges: `./stargazer-users upgrade` with the admin's AWS session, to give every existing project its limits (PR 35, the terms, merged first); it waits on [[retire-stargazer-login-project]], since `upgrade` deploys the login app first

## Not held by the queue

Measured on `u-pryce`, 2026-11-17: a run that names another queue (`queue="default"`) skips the project's queue, and apps don't go through queues: dashboard launches are held to the notebook totals, but an app deployed straight with the project's key isn't. Both are handled by hand if they're abused. The project key can't change its queue or settings (`ACTION_ADMINISTER_PROJECT`, `ACTION_MANAGE_QUEUE`). Which GPU types exist is the tenant's node pools, which the admin chooses: today `awsg52xlarge` (one A10G each) beside the CPU pool `awsr7i2xlarge`. A pool offering another GPU type would leave that type uncapped.

## Verification recipe

As an org admin (`FLYTE_API_KEY` from `~/.flyte/stargazer-upgrade.env`), in the infra worktree, against `u-pryce`:

1. Set small limits on `app.config.LIMIT_*` (e.g. 4 runs, 3 CPU total) and call `ensure_project_limits("u-pryce")`; read back `Queue.get("u-pryce")` and the project's `local_overrides()`. A second call should log no writes.
2. Total cap: wait a minute, submit two tasks of 2 CPU each on an SDK-built image (`flyte.Image.from_debian_base()`) sleeping 90 s, and poll `Queue.details("u-pryce")`: expect `in_flight_resources` cpu `2000m` of `3000m` and the second QUEUED until the first finishes. The release notebook image can't run tasks: a task pod there starts the notebook server instead.
3. No per-task cap: a task asking for 6 CPU / 8Gi reports `cpu.max=600000 100000` from its cgroup.
4. Notebook totals: with `config.FLYTE_PROJECT = "u-pryce"`, serve two small apps named `nb-<x>-edit` (any image; a failed pod still counts by desired state) and call `notebook_budget.refusal("x", "edit", flyte.Resources(cpu=1))` with `config.LIMIT_CPU = "2"`: expect the "needs 1 CPU ... 2 of your 2" refusal, and None at 3. Through the dashboard: launch notebooks until one is refused with that message (needs the test account's terms accepted). Delete the apps after.
5. Put the limits back to `tenant.env`'s and check no runs are live.

## Outcome

Shipped in infra PR 38 (merge `99bb349`): onboarding gives every user project its own Union queue (runs, actions, CPU and memory totals, one A10G) and the dashboard holds open notebooks to the same totals. Verified on the tenant as the test account, as in PR 38; `uv run pytest` 406 passed. The review comment (rework onto Union's own settings and queues) was answered before merge by the queue rework. Left: the rollout, `./stargazer-users upgrade`, is the last step of [[retire-stargazer-login-project]], which has to come first; and a refused launch through the dashboard page itself, unverified behind the test account's terms gate.

Related: [[board]], [[project-costs-daily]], [[retire-stargazer-login-project]].
