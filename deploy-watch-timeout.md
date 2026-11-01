---
title: deploy-watch-timeout
status: done
priority: normal
created: 2026-10-29
pr: 15
---

`stargazer-users upgrade` can hang forever after a dashboard deploy that
succeeded. Infra's `app.deploy.deploy_dashboard` waits on Flyte's serve
watch (`ctx.serve(app_env)`), which has no timeout, and only falls back to
polling `App.get` when the watch raises.

**Measured 2026-10-29** (ticket [[per-user-storage-isolation]], upgrading
`u-pryce`): Knative had revision `dashboard-00001` ready at about 07:01 UTC
(`kubectl get ksvc`, read-only), while Union's app status stayed at
`DEPLOYMENT_STATUS_ASSIGNED` for revision 1348, its lease expiring at
07:01:49. The process sat in the serve watch's stream to the control plane
until it was interrupted, about ten minutes later.

The fix is to bound the watch, then trust `App.get`'s state as the existing
fallback does, failing only if the app isn't active by then. Check it
against a redeploy on the devbox, where a stuck watch can be produced by
stopping the app mid-deploy.

## In review: StargazerBio/infra#15

Branch `fix/deploy-watch-timeout`. Flyte's serve does the build, the deploy and the watch
in one call and has no option to bound the watch. So for the serve's length, `_bounded_watch`
swaps `App.watch` for a copy wrapped in `asyncio.wait_for` (`_WATCH_SECONDS`, 300 s), which
leaves image builds unbounded. When the bound expires it raises `ServeWatchTimeout`, a
`RuntimeError`, and the existing `App.get` polls (24 × 5 s) decide: the endpoint if the
app is active, the error if it never comes up.

**Evidence (measured, 2026-10-30)**
- Unit tests drive Flyte's own serve up to its real `App.watch`, on a stream that never
  answers. Before the fix the deploy hung, blocked in `ctx.serve` (faulthandler at 15 s,
  killed at 35 s). After it, the deploy returns the endpoint, or raises
  `ServeWatchTimeout` when the app stays assigned. `uv run pytest`: 345 passed.
- Devbox A, plain redeploy: the watch answered about 6 s after the deploy, revision 00020 is
  ready and serving 200.
- Devbox B, stopping the app as soon as the deploy lands (this ticket's suggestion): the
  watch does **not** go silent. It raises "has failed!" on the deactivation, and the deploy
  fails at 122.8 s after the polls, as before. The devbox can't produce a quiet stream
  this way.
- Devbox C, bound cut to 1 s on a cold redeploy: the real watch is given up on, the real
  `App.get` finds the app active, and the deploy returns the endpoint at 32.5 s. Revision
  00023 is serving 200.
- Not reproduced: a stream that goes quiet on its own, as Union's did. If Union's status
  stays `ASSIGNED` again, the hang becomes a clear failure after about 7 minutes, not a
  success.

## Verification recipe

On the devbox, `uv run python devbox/dashboard.py` with `app.deploy._WATCH_SECONDS` set
to 1 (a small driver script) on a stopped dashboard. Expect the warning
`Serve for flytesnacks: the serve watch gave no answer in 1.0 s; the app is up`, then the
dashboard's URL, and `kubectl get ksvc -n flyte` ready. Afterwards, redeploy from main.

## Outcome

Shipped in StargazerBio/infra#15 (merge `042d53a`): a dashboard deploy bounds Flyte's
serve watch at `_WATCH_SECONDS` (300 s), leaving image builds unbounded, then lets the
existing `App.get` polls decide, so a watch that never answers ends in the endpoint or a
clear failure instead of a hang. Verified by unit tests on Flyte's real `App.watch` over
a silent stream (it hung before the fix), and on the devbox with the bound cut to 1 s
(the deploy returned the endpoint at 32.5 s). Left: a stream that goes quiet on its own,
as Union's did, wasn't reproduced; it now fails clearly after about 7 minutes. The PR had
no review comments.
