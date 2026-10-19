---
title: Org-wide platform key in every pod
status: backlog
priority: high
created: 2026-10-05
---

Every app and task pod authenticates as `stargazerbio-EAGER_API_KEY-union-us-west-2`, which
holds org-wide `contributor`, so code in any notebook can act in any
project. Ask Union whether an app can run without it or with a key we
supply.

Waiting on Union (2026-10-18).

## Direction

Replace the org key with one key per user, each holding `contributor` on
that user's project only. Pausing a user then means moving their key and
their own login to `viewer` and stopping their apps. Viewer still passes
the dashboard's login gate.

## Findings (2026-10-15 to 2026-10-17)

- The key is the org-scoped secret `EAGER_API_KEY-union-us-west-2`,
  created 2026-09-30 when the tenant was set up. `flyte get cluster-config
  union-us-west-2` shows `unionAuth: {injectSecret: true, secretName:
  EAGER_API_KEY}` in two places: `leaseworker`, which covers task pods,
  and `union-operator` config-overrides `operator.apps.controller`, which
  covers every app pod. Neither config has a per-project or per-app
  exception. `operator.apiKey.enabled: true` is commented as a bootstrap
  loop, so the operator probably recreates the key if it's deleted
  (inferred).
- Task pods get it as `_UNION_EAGER_API_KEY`, and the in-cluster client
  calls as it: `User.get()` returns `393067446845621194`.
- Notebook pods carry it too, as `_UNION_EAGER_API_KEY` in the marimo
  process's env, so a notebook cell can read it (measured 2026-10-18 in
  `nb-key-probe-edit`, ticket `notebook-pinata-key`). The terminal's env
  scrub drops it by its `_KEY` suffix; that's tidiness, not a boundary.
- The dashboard launches notebooks as this key. `creator` is application
  `393067446845621194` on all five `nb-*` apps in `u-pryce`. The dashboard
  itself shows the admin who deployed it.
- Union's injection can't be displaced from our side. Probe in `u-pryce`
  with a key holding `contributor` on `u-pryce` only:
  - A project-scoped secret named `EAGER_API_KEY-union-us-west-2`: the
    pod still got the org key (run `u7fz6jv4l4vlss992mbj`).
  - A project-scoped secret named `EAGER_API_KEY`: same
    (`uz5pklzzwmtnspdn9dp8`).
  - `flyte.Secret(key="SG_PROJECT_API_KEY", as_env_var="_UNION_EAGER_API_KEY")`
    declared on the task env: the secret reached the pod under its own
    name, but the injected value won the collision
    (`ujr67m6pmxv5p52wcp4w`).
  - Torn down afterwards: key, policy, assignment and secrets were
    deleted, and the org secret is unchanged. A baseline run after
    cleanup still gets the org key (`usbrm9csdrwbx56v7fpx`).
  - App pods weren't probed.

## Needs from Union

- Stop injecting the org key into app and task pods, or inject a
  per-project key in its place.
- Whether removing the org key's permissions, or deleting it, breaks
  anything of theirs, such as image builds or the operator's bootstrap.

## Our side, once injection is off

- [ ] `stargazer-users onboard` creates the user's key, its policy, and
  a project-scoped secret holding it; `offboard` removes them.
- [ ] The dashboard and notebooks get the key as `FLYTE_API_KEY`, which
  `app/init.py` already prefers.
- [ ] Task envs declare the secret as `_UNION_EAGER_API_KEY`. Without the
  injected value colliding with it, the SDK should pick it up (inferred
  from the declared-secret probe).
- [ ] `pause` / `resume` in `stargazer-users`.
