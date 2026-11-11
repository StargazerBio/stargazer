---
title: project-pod-env-vars
status: review
priority: normal
created: 2026-11-10
pr: 32
---

A task pod learns where the store and index are, and who owns its outputs, from variables its `TaskEnvironment` forwards from the submitter (`env_vars=STARGAZER_ENV_VARS`). An environment written the way the Flyte docs show has none of them, and the pod then falls back to a store and index on its own disk without saying so. Decided 2026-11-10: these variables are facts about the project, so the project carries them, and a bare `flyte.TaskEnvironment` gets them with no Stargazer code. Secrets stay explicit (`secrets=STARGAZER_SECRETS`) and the image keeps its helper.

This ticket is the infra repo's half. The SDK's half is ticket `bare-task-environments`.

## Current State

- Onboarding already writes the project's `environment_variables` setting, for the pods' role: `project_overrides()` in `stargazer_users/user_role.py` sets `AWS_ROLE_ARN` and `AWS_WEB_IDENTITY_TOKEN_FILE`, merged over the project's other overrides (`update_settings` replaces the whole set). Measured on the tenant 2026-10-29: the setting reaches every task pod in the project.
- The dashboard gives notebook pods `STARGAZER_OWNER`, `STARGAZER_INDEX_URL` and `STARGAZER_STORE_ROOT` in their deploy env (`app/deploy.py`, `app/per_notebook.py`). A task pod gets them only because the notebook's kernel has them and the environment forwards them.

## Plan

- [x] Check the devbox first: does a project's `environment_variables` setting reach a task pod there? Set one by hand, run a bare-environment task that returns `os.environ`, read it back. If it doesn't, the devbox keeps the forwarded variables until it does, and `bare-task-environments` says so in its docs. **Measured 2026-11-10: it doesn't.** The setting is stored (`local_overrides()` returns it) but a bare task's pod has no such variable, 45 s after the write too (runs `r9kkgxncqbjtd96hxfj6`, `rs9dds62vbxwq422r8wz`). The devbox keeps the forwarded variables.
- [x] `project_overrides()` also sets what the SDK forwards today (`_stargazer_env_vars()` in `stargazer.config`): `STARGAZER_OWNER` (the subject), `STARGAZER_INDEX_URL` (`dsql_index_url(project, cluster_arn)`), `STARGAZER_STORE_ROOT` (the workspace root), `STARGAZER_API_KEY_SECRET` (the project's key's secret name) and `PINATA_GATEWAY` when the deploy overrides the SDK's default. One function yields these for both the deploy env and the project setting, so the two can't drift. Shipped as `app.deploy.stargazer_env`, without `PINATA_GATEWAY`: nothing after `stargazer.config`'s import tells an override from the default, and the tenant doesn't override it.
- [x] Tests beside `tests/test_user_role.py`: the overrides hold the five variables for a project, and a project's other variables are kept.
- [ ] Re-run onboarding for existing projects (it's idempotent), the test account's first. `u-pryce` done 2026-11-10 from the branch (`ensure_project_settings` alone, with the org admin's key); every other project needs `./stargazer-users upgrade` with the admin's AWS session, after the PR (infra 32) merges.

## Verification recipe

As the test account on the tenant: a notebook task on a bare `flyte.TaskEnvironment(name=..., image=notebook_image(...))`, with no `env_vars`, dispatched "On the cluster", returns its `STARGAZER_OWNER`, `STARGAZER_INDEX_URL` and `STARGAZER_STORE_ROOT`, and they equal the notebook kernel's. Then a task that stores an asset in one pod and assembles it in the next.

Run 2026-11-10 on the tenant with tasks submitted from a checkout, not a notebook: before, `STARGAZER_OWNER` unset and the store under `/root/.stargazer` (`urwsv2mwp7flmm687dsb`); after, the four variables (`ucts6jp6qfs25lrlx8tg`), a store in one pod (`u9rm87fd5vkb9cpgcjtc`) and an `assemble()` in the next (`usltp9xzdd7xfndfbt6f`). A run started seconds after the settings write still had the old variables (`u6r7d2fpk6fx5gqdjjlm`). The notebook path isn't driven yet.

Related: [[board]], [[bare-task-environments]], [[task-environment-factory]], [[flyte-task-environments]].
