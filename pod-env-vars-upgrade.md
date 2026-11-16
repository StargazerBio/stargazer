---
title: pod-env-vars-upgrade
status: done
priority: high
created: 2026-11-16
---

Ticket [[project-pod-env-vars]] (infra PR 32) moved Stargazer's variables into each project's `environment_variables` setting, and ticket [[bare-task-environments]] (PR 149) dropped `env_vars=` from the template and the tasks tutorial notebook. Only `u-pryce` got the new setting (2026-11-10). Every other project needs `./stargazer-users upgrade`, run from infra with the org admin's AWS session; until then a bare-environment task in those projects raises that it has no store or index. Whether it has already run isn't recorded (not checked, 2026-11-16).

Verify: for each project, its settings' `environment_variables` hold `STARGAZER_OWNER`, `STARGAZER_INDEX_URL` and `STARGAZER_STORE_ROOT` beside the role's variables.

## Outcome

Nothing to run. Checked 2026-11-16 as the org admin, read-only (`Project.listall()` and each `u-*` project's `Settings.get_settings_for_edit(...).local_overrides()`): `u-pryce` is the tenant's only active user project, and its `environment_variables` hold `STARGAZER_OWNER`, `STARGAZER_INDEX_URL`, `STARGAZER_STORE_ROOT` and `STARGAZER_API_KEY_SECRET` beside the role's variables (measured). New projects get them from onboarding.

Related: [[board]], [[project-pod-env-vars]], [[bare-task-environments]].
