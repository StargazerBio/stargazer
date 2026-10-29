---
title: launch-delete-while-serving
status: maybe
priority: low
created: 2026-10-29
---

Deleting a workspace notebook removes its launch rows (ticket
`launch-row-on-delete`), but not a serve already under way. When a
notebook's image build has finished and the dashboard is serving its pod
(`_serving` in infra's `app/admin_app.py`), a delete in that window leaves
the serve running: the serve's own settle finds the row gone and writes
nothing, but the pod being served can still come up for a notebook that no
longer exists. Not reproduced; deferred from StargazerBio/infra#13. The fix
would cancel or stop the serve on delete, or stop the app once it settles
with no row.
