---
title: launch-row-on-delete
status: backlog
priority: low
created: 2026-10-28
---

Deleting a workspace notebook (`/workspace/delete` in infra's `app/admin_app.py`) leaves its `launch:<slug>:<mode>` rows in the owner's state table. `/launch/status` keeps reporting them: a failed one forever, and a pending one is looked up by its build run on every poll. Seen on the tenant: `lbs-fail-1027`, deleted earlier, was still reported as failed on 2026-10-28. Nothing shows it, since there's no tile, but a notebook created again under the same slug would show the old failure. Delete should remove both modes' rows.
