---
title: dashboard-naming
status: done
priority: low
created: 2026-11-22
pr: 49
---

The per-user dashboard went by three names: Union serves it as `dashboard`, but infra's module was `app/admin_app.py` and its AppEnvironment `app_env`, though it isn't an admin app. Infra PR #49 makes it `app/dashboard.py`, `dashboard_env` (beside `login_env`), the page handler `dashboard_page` and `tests/unit/test_dashboard.py`, with the docs following. The served name and image are unchanged.

## Verification recipe

From the infra worktree with `tenant.env` loaded: `uv run python .claude/skills/verify-dashboard/scripts/union_dashboard.py deploy`. The app's served args say `app.dashboard:asgi_app` and it reaches `Service is ready`. Open the dashboard from the signed-in console; the page renders and `/health`, `/launch/status` and `/assets/schema` answer 200 from it. Then `union_dashboard.py teardown`.

## Outcome

Shipped in infra PR 49 (merge `0d1687c`): `app/dashboard.py`, `dashboard_env`, `dashboard_page` and `tests/unit/test_dashboard.py`. Verified: unit tier 447 passed, and the test account's dashboard deployed from the branch served `app.dashboard:asgi_app`, reached `Service is ready`, and answered 200 on `/health`, `/launch/status` and `/assets/schema` (measured). Nothing left.

Related: [[board]]
