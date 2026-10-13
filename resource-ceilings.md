---
title: Resource ceilings for notebooks and runs
status: doing
priority: high
created: 2026-10-13
---

Notebook pods and task runs on the tenant get whatever they ask for. A
notebook's `[tool.stargazer]` header, or the create form, can request any CPU
and memory, and so can any task a notebook runs. Cap both at **4 CPU / 16 GiB**
(decided 2026-10-13): room for the scRNA env's 6 GiB limit, and a cheap worst
case per user during the alpha. Split out of
[union-production-deploy](union-production-deploy.md).

## What Union's setting covers (measured 2026-10-13)

Probe: a task and an app in `u-387300641116005877`/development (the test
account's archived first project; runs and apps still work in it), each asking
for 2 CPU / 2Gi, reporting their cgroup `cpu.max` and `memory.max`. Then a
project-scoped `task_resource.max.cpu: 1`, `task_resource.max.memory: 1Gi`,
and the same again.

| | No cap | Capped at 1 CPU / 1Gi |
|---|---|---|
| Task | 2 CPU / 2Gi | **1 CPU / 1Gi**, silently (no error, run succeeded) |
| App, new revision | 2 CPU / 2Gi | **2 CPU / 2Gi**: not capped |

So `task_resource.max.*` binds runs but not apps. Notebook pods are apps, and
the dashboard is what sets their resources, so the dashboard has to cap them.

Two settings-file quirks seen on the way: `~unset` doesn't remove an override,
it pins the key to empty and blocks inheritance from the domain; to inherit
again, comment the line out in a `flyte get settings -o` dump and apply that.
The test project was put back that way (diffed against the dump taken before).

## Pieces

- [x] The dashboard clamps notebook resources to the ceiling
      (`app.notebook_meta.MAX_RESOURCES`): header values on launch, and the
      create and settings forms. Memory is compared by size whatever its unit;
      an unreadable quantity falls back to the default, since it can't be
      checked against the cap. `feat/resource-ceilings` 3d7af27, unit tests.
- [x] The settings form's number inputs carry the ceiling as `max`.
- [x] `task_resource.max.cpu: "4"`, `task_resource.max.memory: "16Gi"` on the
      tenant's development domain, set 2026-10-13 (the domain had no
      overrides before). Probe task asking for 6 CPU / 20Gi in
      `u-387300641116005877` got `cpu.max 400000 100000`, `memory.max
      17179869184`: 4 CPU / 16 GiB (run `uskdlqp49vfpt2dltbc5`).
- [x] Docs: `app_internals.md` (the domain setting, in Deploy Settings),
      `docs/architecture/app.md`, the `notebook_meta`/`per_notebook`
      docstrings that said "no ceiling", the blank seed's docstring.
- [ ] Verified on the tenant: a notebook asking for more than the ceiling
      launches with 4 CPU / 16Gi.

## Not covered

The dashboard cap is a guardrail, not a boundary. The user's `contributor`
role on their project, and the org-wide key in every pod
([org-wide-platform-key](org-wide-platform-key.md)), can deploy an app with
any resources directly. Capping apps server-side would take a per-namespace
`LimitRange`, which Union manages; ask Union whether it can set one.
