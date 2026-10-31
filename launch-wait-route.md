---
title: launch-wait-route
status: review
priority: high
created: 2026-10-31
pr: 27
---

Opening a stopped notebook from the dashboard opened a bare 404. The serve's watch fails at once under the project key (`ACTION_VIEW_FLYTE_EXECUTIONS` denied), and `_serve`'s fallback handed back the endpoint before the app's route existed. A stopped app has no route until its pod is ready: 13 s on a node with the image, 91 s on one pulling it. Fix in StargazerBio/infra#27 (`fix/launch-wait-route`): `/launch` answers 202 `starting` until the app is active, and the tile polls `/launch/status` until it's running.

## Verification recipe

On the tenant as the test account, with the branch's dashboard deployed (`union_dashboard.py deploy`):

1. Stop a workspace notebook: `flyte --config .flyte/union.yaml update app nb-<slug>-edit --deactivate -p u-pryce -d development --wait`. Its address answers 404 to `curl`.
2. Click Edit on its tile. The dashboard's log shows `POST /launch` 202, then `GET /launch/status` every 5 s.
3. Poll the address with `curl` until it answers 302. The tile turns to Open only after that, and Open loads the editor.
4. Stop the notebook again.
