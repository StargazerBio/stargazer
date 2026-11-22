---
title: project-costs-daily
status: doing
priority: low
created: 2026-10-28
---

Run the per-project cost report (ticket [[project-costs]], the `project_costs` task in infra's `admin` project) on a daily schedule, with Flyte's own trigger, so an admin no longer starts it by hand. Showing each user their project's share on their dashboard is ticket [[project-costs-on-dashboard]].

## Plan

- [x] `flyte.Trigger.daily()` on `project_costs` (midnight UTC, the latest period), registered by `stargazer-costs deploy`
- [x] Deployed to `admin` on the tenant: `flyte get trigger` lists `daily`, `cron: 0 0 * * * (UTC)`, `active: true`
- [ ] A scheduled run seen to succeed after the first midnight UTC

## Verification recipe

1. From infra's worktree, `AWS_PROFILE=claude ./stargazer-costs deploy`.
2. `flyte --config .flyte/union.yaml get trigger costs.project_costs daily -p admin -d development`: `cron 0 0 * * *`, timezone `UTC`, `active: true`, `task_version` the deploy's.
3. `AWS_PROFILE=claude ./stargazer-costs run` and wait for it to succeed: the deployed version still runs.
4. After the next midnight UTC, `flyte --config .flyte/union.yaml get run -p admin -d development` lists a run started by the trigger, succeeded.

Related: [[board]], [[project-costs]], [[project-costs-on-dashboard]].
