---
title: Org-wide platform key in every pod
status: done
priority: high
created: 2026-10-05
pr: 82
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

## Union turns the org key off (2026-10-21)

Union will turn off the org key's injection and stop it being recreated, so
the org-wide key goes away. Pods then get only a project-scoped
`EAGER_API_KEY` (measured during the experiment below), and a project
without one can't start pods, so onboarding has to create each user's key.
That's what branch `fix/org-wide-platform-key` does (The project key,
below). Parked until the user confirms Union has turned the org key off.

The branch holds the per-project key code, unpushed in its worktree, last
rebased onto `main` at `2b96e0e` on 2026-10-20 (unit tier 508 passed); it
needs rebasing onto today's `main` before its PR. It also carries a rider from ticket `quickstart-save-banner`, which
its PR lists under its own heading: "Stage the image's notebooks as
/opt/notebooks and copy the folder itself" (`Dockerfile` only; the image's
`/workspace/notebooks/` comes out the same, verified on its original
commit `41c03a4`). It's harmless while the org secret exists, since that one wins.
Its `app/onboard.py` changes predate onboarding's move to infra (ticket
`onboarding-to-infra`): when it's unparked, the key creation goes into infra's
`stargazer_users/onboard.py`, and only what's left of the branch stays in
stargazer.

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
  bootstrap loop) and stop it. Union is turning off the injection and the
  recreation (2026-10-21); check the org secret stays gone afterwards.
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

## Union turned injection off (2026-10-22)

The user confirmed it, and `flyte get cluster-config union-us-west-2` shows
`unionAuth: {injectSecret: false, secretName: EAGER_API_KEY}` in both
`leaseworker` and `operator.apps.controller`. The org secret
`EAGER_API_KEY-union-us-west-2` is still in Secrets Manager (created
2026-10-20 10:10), and its key `393067446845621194` still exists, but no
pod gets it.

- Pods start without any key: nothing refuses them now.
- A pod without a key has no identity. A parent task's child launch fell
  back to a browser sign-in and failed on its localhost callback
  (`address already in use`), twelve attempts in a row (run
  `u9xjvq5xth227xmngxwv` in `u-pryce`, aborted). So every workflow with
  child tasks on Union broke, and #81's dashboard hung on its in-pod image
  build.
- The project `EAGER_API_KEY` secrets from 2026-10-20 aren't injected
  either: only the org-wide switch did that.

## The project key (branch `fix/org-wide-platform-key`, infra `08dcab3`)

Every pod declares its project's key itself. On the `union` target
`STARGAZER_SECRETS` (`stargazer.config`) adds
`flyte.Secret(key="UNION_API_KEY", as_env_var="_UNION_EAGER_API_KEY")`, the
variable flyte's `init_in_cluster` reads first; task environments, the
dashboard and notebook pods all share the list. The devbox declares none,
since its webhook refuses a pod whose declared secret is missing.

Infra's `onboard` and `upgrade` give a project without the secret its key:
API key `stargazer-<project>`, created without Union's default policies and
assigned the user's `stargazer-<project>` policy, stored as the project's
secret `UNION_API_KEY` (`PROJECT_KEY_SECRET`) in the deploy domain. Any key
left from an earlier try is deleted first, since a key's value can't be read
back, and a key whose secret fails to land is deleted. `offboard` deletes
the key and its secret. The secret isn't `EAGER_API_KEY`, which Union's
control plane hides and can't delete; `UNION_API_KEY` is the name
`flyteplugins.union` gives the value, and it reads back and deletes like any
other secret. One domain only: the user's policy covers `FLYTE_DOMAIN`, and
their dashboard, notebooks and runs are all there.

### Measured 2026-10-20, while Union injected project keys

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

- [x] Every Union pod declares its project's key (stargazer `f0edb6e`).
- [x] `onboard` and `upgrade` give a project without one its key and
  secret; `offboard` removes them (infra `08dcab3`, 24 tests).
- [x] Verify on Union (2026-10-22, test account, branch at `f0edb6e`):
  - `./stargazer-users upgrade` with `STARGAZER_CHECKOUT` on the branch
    replaced `u-pryce`'s 10-20 key with `396274977512389267`, whose only
    policy is `stargazer-u-pryce`, wrote the secret, and redeployed the
    dashboard. Its spec references `UNION_API_KEY` and `PINATA_JWT` by name
    only.
  - The notebook and dashboard images built in `flytesnacks`, which has no
    key: image builds need none.
  - A keyed parent launched its child in 13 s (run `uglnjvlhjtrvlws4khgd`).
    From that pod the key was refused listing runs and starting one in
    `flytesnacks` ("permission denied … Identity: app/396274977512389267").
  - A Basic notebook ("Key 1022") launched from the dashboard: its image
    built in `u-pryce` as `stargazer-u-pryce` (run `unsmh2c2t4kwgr4gjmd2`),
    the app's `creator` is the key, and section 0 read
    `bcftools → /usr/bin/bcftools`.
  - The Execution tutorial's remote run from its notebook kernel,
    `audit_cohorts` with three `summarize_cohort` children, succeeded as
    the key (run `uzdk7d4z6vmjjk4n6svz`).
  - Torn down: both notebooks and the dashboard stopped, no live runs. The
    notebook "Key 1022" is left in the test account's workspace.
- [x] Delete the org secret `EAGER_API_KEY-union-us-west-2` (the user,
  2026-10-24). Before, a `u-pryce` task declaring it got it (run
  `uxs49wn5ht5x4shbqwbp`, checked set/unset only); now the pod webhook
  refuses such a task at admission (run `u2wqkphhwpqw6x9nz44c`).
- [ ] Delete the org key `393067446845621194` (an admin's step). It still
  holds org-wide `contributor`, so any copy of it taken while Union
  injected it still works. The admin console doesn't list it (nor
  `stargazer-flytesnacks`); `ApiKey.delete` under an admin login does.
- [ ] Clean up what the injection era left: the `EAGER_API_KEY` secrets in
  `u-pryce` and `flytesnacks` (three domains each, in Secrets Manager only)
  and key `stargazer-flytesnacks`.
- [ ] `pause` / `resume` in `stargazer-users`.

## Outcome

Shipped in PR #82 (`f0edb6e`, merged 2026-10-24 as `403fefb`) and infra
`08dcab3` and `48c18be` (pushed 2026-10-24). On Union every pod declares its
project's key, secret `UNION_API_KEY`, as `_UNION_EAGER_API_KEY`.
`stargazer-users` `onboard` and `upgrade` create the key, holding only the
project's policy, and its secret; `offboard` deletes both. `48c18be` lifts
`ApiKey.listall`'s 100-key cap, found after the PR by checking the tests'
fakes against Union's API.

Verified on Union with the test account (Our side, above): `upgrade` keyed
`u-pryce`, a parent launched its child, the key was refused in
`flytesnacks`, and a dashboard notebook launched and its kernel's remote run
succeeded, all as the project key. The user deleted the org secret on
2026-10-24. Not run on Union: `onboard` for a new user and `offboard`, which
create and archive projects that can't be deleted, and registering a task or
serving an app in another project under the project key.

Left: deleting the org key and the injection era's other keys and secrets
(ticket `retire-org-key`), and `pause` / `resume` (ticket
`pause-resume-users`).
