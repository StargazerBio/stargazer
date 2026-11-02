---
title: launch-row-on-delete
status: done
priority: low
created: 2026-10-28
pr: 13
---

Deleting a workspace notebook (`/workspace/delete` in infra's `app/admin_app.py`) leaves its `launch:<slug>:<mode>` rows in the owner's state table. `/launch/status` keeps reporting them: a failed one forever, and a pending one is looked up by its build run on every poll. Seen on the tenant: `lbs-fail-1027`, deleted earlier, was still reported as failed on 2026-10-28. Nothing shows it, since there's no tile, but a notebook created again under the same slug would show the old failure. Delete should remove both modes' rows.

In review as StargazerBio/infra#13: the delete's teardown deletes both modes' launch rows. Verified on the tenant: recreating `lbs-fail-1027` and `lfol-fail-1028` brought their old failures back on the new tiles, and deleting them through `/workspace/delete` cleared `/launch/status`.

## Outcome

Shipped in StargazerBio/infra#13 (merge `8ec8d88`): deleting a workspace
notebook also deletes its `launch:<slug>:edit` and `launch:<slug>:run`
rows, best-effort like the pod teardown. Verified by
`test_deleting_a_notebook_forgets_its_launches` (fails without the fix;
unit tier 336) and on the tenant as the test account: two deleted
notebooks' stale failures cleared from `/launch/status` after a delete
from the fixed dashboard. No comments on the PR. Left: a delete while the
pod is being served (ticket [[launch-delete-while-serving]]).

Related: [[board]].
