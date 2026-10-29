---
title: launch-row-on-delete
status: review
priority: low
created: 2026-10-28
pr: 13
---

Deleting a workspace notebook (`/workspace/delete` in infra's `app/admin_app.py`) leaves its `launch:<slug>:<mode>` rows in the owner's state table. `/launch/status` keeps reporting them: a failed one forever, and a pending one is looked up by its build run on every poll. Seen on the tenant: `lbs-fail-1027`, deleted earlier, was still reported as failed on 2026-10-28. Nothing shows it, since there's no tile, but a notebook created again under the same slug would show the old failure. Delete should remove both modes' rows.

In review as StargazerBio/infra#13: the delete's teardown deletes both modes' launch rows. Verified on the tenant: recreating `lbs-fail-1027` and `lfol-fail-1028` brought their old failures back on the new tiles, and deleting them through `/workspace/delete` cleared `/launch/status`.
