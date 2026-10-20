---
title: Org-wide platform key in every pod
status: backlog
priority: high
created: 2026-10-05
---

Every app and task pod authenticated as `stargazerbio-EAGER_API_KEY-union-us-west-2`, which
holds org-wide `contributor`, so code in any notebook could act in any
project.

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

## Parked (2026-10-20)

Set aside by the user while the org secret keeps coming back. Branch
`fix/org-wide-platform-key` holds the per-project key code, unpushed in its
worktree. It's harmless while the org secret exists, since that one wins.
Its `app/onboard.py` changes overlap `dsql-asset-index`'s onboarding piece,
so whichever of the two lands second rebases on the other.

## Experiment: delete the org key (2026-10-20)

The user deleted the org secret `EAGER_API_KEY-union-us-west-2`. The
key it held (`393067446845621194`) still exists, and the operator hadn't
recreated the secret an hour later.

- [x] A project with no `EAGER_API_KEY` at any scope can't start pods:
  *"admission webhook "flyte-pod-webhook.flyte.org" denied the request:
  none of the secret managers injected secret [key:"EAGER_API_KEY"]"*
  (run `uvld5kwd76ppkp66f4qk` in `flytesnacks`). That's every project
  that isn't onboarded, including Union's own `default`, `system` and
  `union-health-monitoring`.
- [x] With the org secret gone, the webhook injects a project-scoped
  secret named `EAGER_API_KEY`. The 10-17 probe's copy in
  `u-pryce/development` had stayed in AWS Secrets Manager after the SDK
  delete, and pods got its dead key (`invalid_client`, run
  `ud4f96qvcj2564zv7pc9`). Writing the secret again replaced it.
- [x] App pods follow the same rule: the dashboard and notebook pods in
  `u-pryce` carry the project's key as `_UNION_EAGER_API_KEY` (read from
  the pod specs with kubectl, client ids only).
- [x] Image builds run as task pods in the deployer's project
  (`flytesnacks`), so that project needs its own key. With one, the
  notebook and dashboard images built.
- [ ] Ask Union whether `default`, `system` and
  `union-health-monitoring` need a key, or whether they'd rather have the
  org secret back.

- [x] Union's control plane hides every secret named `EAGER_API_KEY`:
  `Secret.get` and `Secret.delete` are `NOT_FOUND` and `listall` and the
  console leave it out, even right after it's written. Other names read
  back at once. The secrets are still in AWS Secrets Manager and injected,
  and writing one again overwrites it (CloudTrail shows only
  `CreateSecret`/`UpdateSecret`). That's why the 10-17 probe's copy
  survived its delete, and why the console shows only `PINATA_JWT`.

- [x] The org secret came back. `EAGER_API_KEY-union-us-west-2` was
  created again at 10:10:04 PDT, holding the original key
  `393067446845621194`. The write came through the control plane:
  CloudTrail shows `adminflyterole`, under the same session that wrote the
  project secrets, so it doesn't say who asked. It wins over the project
  secrets, so from then on pods called Union as the org key again. Nothing
  failed; the isolation was silently gone.
- [ ] Find out what recreated it (the user, Union, or the operator's
  bootstrap loop) and stop it.
- [ ] Cross-project writes under the project key. The read check passed
  (`ACTION_VIEW` refused on other projects), but the write probe (run
  `urdpj55wqsm25nbs7r5t`: register a task, start a run and serve an app in
  `flytesnacks` from a `u-pryce` pod) ran after 10:10. All three
  succeeded, and the app's `creator` was the org key, so it says nothing
  about the project key. Rerun once the org secret stays gone (script:
  a task that calls `flyte.deploy`, `with_runcontext(project=…).run` and
  `with_servecontext(project=…).serve` for another project).
- [x] Pods can't read other projects' secrets from AWS: `GetSecretValue`
  is implicitDeny for the pod role `userflyterole` and every node role,
  and the user-workload nodes set the metadata hop limit to 1.

## The project key (branch `fix/org-wide-platform-key`)

`onboard` gives each user's project API key `stargazer-<project>`. The key
is created without Union's default policies and assigned the user's
`stargazer-<project>` policy, which holds `contributor` on each of the
project's three domains. It's stored as `EAGER_API_KEY` in each domain,
because neither a secret nor a role binding can name a project without a
domain. `upgrade` does the same for any project that lacks a key, and
both commands key the deployer's build project first. Since the secrets
can't be read back, an existing key is what says a project is done.
Re-running keeps it, measured by key ids before and after. `offboard`
deletes the key, and its secrets stay behind holding a dead key.

Measured on 2026-10-20 after onboarding the test account from the branch:

- Task pods in `u-pryce` (`development` and `staging`) and in
  `flytesnacks` got their own project's key and could call Union. They
  were refused `ACTION_VIEW_FLYTE_EXECUTIONS` on every other project (runs
  `utssqhldj9tvq9zkzxlh`, `ut474sn9pcdnrbf5bzt7`).
- A notebook launched from the dashboard for the first time
  (`nb-assets-run`) records the `u-pryce` key (`395974305206254348`) as its
  `creator`. `/launch/status` lists apps under it.
- `u-pryce`'s policy was migrated by hand from a `development`-only
  binding to all three domains. It's the only project that had the old
  binding.

## Our side

- [x] `stargazer-users onboard` creates the user's key, its policy, and
  the project secrets holding it. `offboard` removes them, and `upgrade`
  creates them for any project without them.
- [x] Dashboard, notebook and task pods get the key from Union's injection,
  with nothing declared on their envs.
- [ ] `pause` / `resume` in `stargazer-users`.
