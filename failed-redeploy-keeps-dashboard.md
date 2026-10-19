---
title: A failed redeploy leaves the old dashboard serving
status: maybe
priority: low
created: 2026-10-19
---

Since the index lease (ticket `stale-dashboard-revisions`), the old dashboard
pod stops as soon as the new one claims the lease, before the new one has
restored or started its server. If the new revision then fails (a bad image,
an import error, a failed restore), the dashboard stays down until a working
deploy. Before the lease, Knative kept routing to the old revision until the
new one was ready.

`deploy_dashboard` reports a deploy that never goes active, and a release is
tried on the test account first, so this needs a broken release to slip past
both. If it's worth closing, two options:

- The new pod checks itself before claiming: import `app.admin_app` in a
  subprocess and restore into a scratch file. That adds a few seconds to every
  cold start.
- The old pod takes the lease back if the new holder hasn't started serving
  within some time. That needs the holder to say when it's serving.
