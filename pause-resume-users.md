---
title: pause-resume-users
status: done
priority: normal
created: 2026-10-24
---

`stargazer-users pause` and `resume` in infra. Pausing moves the user's login and their project key (`stargazer-<project>`) from `contributor` to `viewer` on their project and stops their apps. Viewer still passes the dashboard's login gate, so the user can look but not run anything. Resuming moves both back and redeploys their dashboard. From ticket [[org-wide-platform-key]]'s direction.

## Outcome

Shipped in infra `d9c039c` (2026-10-25): `stargazer-users pause` and `resume`. Pause turns every binding of the project policy `stargazer-<project>`, which the user's login and the project key share, from `contributor` to `viewer`, then stops the project's apps. Resume turns them back and redeploys the dashboard. `upgrade` skips a paused user and `onboard` refuses one. `Policy.bindings` drops a project binding's domain, and `stargazer-u-pryce` binds staging, production and development, so the bindings are read from the protobuf and every one is switched.

Verified on Union with the test account. After `pause`, all three bindings were `viewer` and every `u-pryce` app was inactive; a `u-pryce` task holding the project key listed runs, but its child launch was refused, `PERMISSION_DENIED` on `ACTION_CREATE_FLYTE_EXECUTIONS` (run `ucq22nk5qvczkrllx9bv`). After `resume`, all three were `contributor`, the dashboard answered with its login redirect, and the same probe's child ran (run `usmczs59hvkm9nvb6kzl`). The dashboard was stopped afterwards. Not checked: the paused user's own view of the Union console.

Left: pause doesn't stop runs already going. Their child launches are refused, and Flyte retries each one up to 100 times with backoff instead of failing.
