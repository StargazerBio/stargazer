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

Union can't scope or replace the key today (support ticket 7183). Their
proper fix is per-user identity for task pods, written up in
[Union Delegated Auth](https://app.notion.com/p/EXTERNAL-Union-Delegated-Auth-Per-User-Identity-for-Task-Pods-3df8cc06513d81aa96b8e7943b6924da),
with no ETA yet. Meanwhile we're testing the interim route ourselves:
delete the org key and hand each user's pods a key scoped to their
project.

It also limits the per-user index isolation in ticket `dsql-asset-index`:
a pod can start a run in another user's project, and that run's pods carry
that project's service-account token, which is what the user's index role
trusts.

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

## Union's answer (2026-10-20)

- Per-project injected keys aren't possible today. Delegated auth
  (above) is the real fix and covers attribution and key expiry, which
  the interim route gives up.
- Deleting the org key will probably break deploys: the pod webhook
  still tries to mount `EAGER_API_KEY` into every pod and fails early.
  The switch is `leaseworker.unionAuth.injectSecret: true` (and its twin
  in `operator.apps.controller`, from the findings above); Union would
  have to check whether it can be turned off for us.
- Webhook failures from our testing won't page their on-call, so the
  experiment is ours to run.
- Union would rather we wait for delegated auth, and isolation between
  users isn't guaranteed until then.

## Experiment: delete the org key

- [ ] Before deleting, record the org secret's metadata and the key's
  app id (`393067446845621194`) and roles, so it can be recreated.
- [ ] Delete the org secret `EAGER_API_KEY-union-us-west-2`.
- [ ] A task run in `u-pryce`: does the pod start, or does the webhook
  reject it? If it starts, is `_UNION_EAGER_API_KEY` absent, or set from
  a declared project secret?
- [ ] An app deploy and a notebook launch from the dashboard: same
  questions for app pods, which weren't probed before.
- [ ] Wait out the operator's bootstrap loop (`operator.apiKey.enabled`)
  and check whether it recreated the secret.
- [ ] Image builds still work.
- [ ] Rollback if pods won't start: create a new key with org
  `contributor` via `ApiKey.create` and store it as the org secret
  `EAGER_API_KEY-union-us-west-2`, then confirm a baseline run gets it.

If pods can't start without the injected secret, this waits on Union
turning `injectSecret` off or shipping delegated auth.

## Our side, once the org key is gone

- [ ] `stargazer-users onboard` creates the user's key, its policy, and
  a project-scoped secret holding it; `offboard` removes them.
- [ ] The dashboard and notebooks get the key as `FLYTE_API_KEY`, which
  `app/init.py` already prefers.
- [ ] Task envs declare the secret as `_UNION_EAGER_API_KEY`. Without the
  injected value colliding with it, the SDK should pick it up (inferred
  from the declared-secret probe).
- [ ] `pause` / `resume` in `stargazer-users`.
