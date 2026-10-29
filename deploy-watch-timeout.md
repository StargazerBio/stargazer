---
title: deploy-watch-timeout
status: backlog
priority: normal
created: 2026-10-29
---

`stargazer-users upgrade` can hang forever after a dashboard deploy that
succeeded. Infra's `app.deploy.deploy_dashboard` waits on Flyte's serve
watch (`ctx.serve(app_env)`), which has no timeout, and only falls back to
polling `App.get` when the watch raises.

**Measured 2026-10-29** (ticket `per-user-storage-isolation`, upgrading
`u-pryce`): Knative had revision `dashboard-00001` ready at about 07:01 UTC
(`kubectl get ksvc`, read-only), while Union's app status stayed at
`DEPLOYMENT_STATUS_ASSIGNED` for revision 1348, its lease expiring at
07:01:49. The process sat in the serve watch's stream to the control plane
until it was interrupted, about ten minutes later.

The fix is to bound the watch, then trust `App.get`'s state as the existing
fallback does, failing only if the app isn't active by then. Check it
against a redeploy on the devbox, where a stuck watch can be produced by
stopping the app mid-deploy.
