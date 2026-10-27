---
title: A workspace notebook can share a built-in notebook's app name
status: done
priority: normal
created: 2026-10-26
pr: 93
---

A notebook's pod is named `nb-<slug>-<mode>` whatever its section, and
`_notebook_slug` in `app/admin_app.py` reserves only the seed slugs. So a
workspace notebook named `assets`, `tasks`, `workflows`, `execution` or
`scrna-pipeline` (by Create, or by Open from GitHub, where a built-in
tutorial's file stem is exactly its slug) gets the same app names as the
built-in notebook. Launching one serves over the other's app, and the launch
status hydrates both tiles as running. Pick one: reserve the built-in slugs
too, or give workspace apps a distinct name.

Decided 2026-10-26: reserve the built-in slugs (from the `app.notebooks`
catalog) where a new name is chosen (Create, Copy) via `_new_notebook_slug`; the guard on existing slugs is unchanged. Create refuses a
reserved name with "taken by a built-in notebook"; apps aren't renamed.

- [x] Tests: a workspace notebook named after a built-in tutorial is refused and nothing is stored; every built-in slug is reserved
- [x] `_new_notebook_slug` reserves every built-in slug for Create and Copy; Create's message
- [x] A notebook already stored under a built-in slug can still be downloaded and deleted (test)
- [x] Verified on the test account's Union dashboard (2026-10-26, dashboard at 0eb3f8a): R1 and R2 pass; the probe notebook deleted; teardown stopped the dashboard, live runs `[]`

## Verification recipe: built-in names refused on Create

Create on the Workspace section refuses a name whose slug is a built-in
notebook's, so a workspace notebook never shares a built-in notebook's app.

### Sub-features
- R1: Create named "Assets" is refused with `"Assets" is taken by a built-in notebook. Pick another name.` and no tile appears
- R2: Create with an ordinary name still adds a tile

### How to get to it (user POV)
Dashboard → Workspace → New notebook tile → name → Create.

### Driving it
1. From the worktree root, deploy the test account's dashboard: `(set -a; . ~/Desktop/stargazerbio/infra/tenant.env; set +a; STARGAZER_TARGET=union uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy)` → prints the dashboard URL; its footer shows the commit.
2. On the dashboard page, `fetch("/workspace/create", {method: "POST", body: new URLSearchParams({name: "Assets", source: "blank"})})` → 400 with R1's message; the same through the New notebook form → alert with it (override `window.alert` to capture it in the built-in browser).
3. Create an ordinary name (e.g. `slug probe`) → 200 and a tile (R2). Delete it from its tile.
4. `union_dashboard.py teardown` → live runs `[]`.

### Gotchas
- A workspace notebook already stored under a built-in slug stays manageable (only new names are refused), but still shares the built-in notebook's app until the user renames it.

## Outcome

Shipped in PR #93 (merge `68c8ac9`). Create and Open from GitHub refuse a built-in notebook's name (400 and 409, "is taken by a built-in notebook"), so a new workspace notebook can't share a built-in notebook's app. Its last commit renamed shipped notebooks to built-in notebooks throughout (`shipped_source` → `builtin_source`). Verified by the unit tier (539 passed, four new tests) and on Union with the test account's dashboard (the recipe above). Left: a workspace notebook already stored under a built-in name still shares that app until it's renamed, ticket `stored-builtin-slug-notebooks`. No review comments.
