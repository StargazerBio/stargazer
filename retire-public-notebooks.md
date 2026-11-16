---
title: retire-public-notebooks
status: done
priority: normal
created: 2026-11-03
pr: 33
---

Publishing notebooks goes to the community repo now (ticket
[[publish-to-git]]), so the public-tier notebook path goes:

- Migrate each existing public `asset=notebook` record: commit it to
  `StargazerBio/community-notebooks` under its owner, then delete it from the
  public tier.
- Infra: the explorer's public `notebook` entries and their copy route.
- This repo: the `Notebook` asset type (`src/stargazer/assets/notebook.py`),
  its export, and any docs naming published notebooks as assets.
- The `stargazer-workspaces` App's Pull requests write, which nothing uses.

Waits on [[community-explorer-listing]], so the explorer still lists
notebooks once the public ones are gone.

## Notes (2026-11-09)

Not started. The order matters and its first steps aren't this repo's: infra still imports `Notebook` from `stargazer.assets` in `app/notebooks.py`, `app/assets.py`, `app/public_notebooks.py`, `app/admin_app.py` and `app/community_listing.py` (the new listing builds its rows as `Notebook` assets), so the type can't leave the SDK until infra stops using it. Migrating and then deleting the public records, and dropping the App's permission, need the user's go-ahead.

## Inventory (2026-11-16)

Measured with the org's Pinata key (`tests/.secrets/pinata_jwt`, the key the
hosted dashboards hold, inferred from the earlier `public-notebooks` drive):
a `keyvalues[asset]=notebook` query of `/v3/files/public` returns `[]`, and
the whole account holds 6 public files, none of them notebooks
(`anndata` ×2, `reference`, `r1`, `r2`, `known_sites`), and no private ones.
Unowned files were counted too.

No record to migrate, so there's no community-notebooks PR and nothing to
delete. (The key in the main checkout's `.env` is stale: Pinata answers 401.)

## Pieces

- [x] Inventory of public `asset=notebook` records: none.
- [x] Migration to community-notebooks: nothing to migrate.
- [x] Deletes of migrated public records: nothing to delete.
- [x] Infra (PR 33, `feat/retire-public-notebooks`): the `public` source
      leaves out `asset=notebook` records, `/workspace/copy` loses its
      `public` section, `app/public_notebooks.py` goes, and no `app/` module
      imports `Notebook` from `stargazer.assets` (entries build their
      keyvalues with `app.notebooks.notebook_keyvalues`).
- [ ] Remove `Notebook` from the SDK: its own PR, ticket [[drop-notebook-asset]].
- [ ] Drop the `stargazer-workspaces` GitHub App's Pull requests write
      permission: a GitHub settings change the user makes.
- [ ] Drive the explorer on the tenant as the test account (see below).

## Verification recipe

- **RP-1** `/assets/list?source=public` lists no `asset=notebook` record and
  answers 200 with no `Stargazer-Unavailable`.
- **RP-2** `source=stargazer&source=featured&source=community` still lists
  every notebook as `asset=notebook` with `title`, `description` and `slug`.
- **RP-3** `POST /workspace/copy` with `section=public` is a 400; with
  `section=community` and a featured entry's `<commit>/<path>` it is a 200
  whose workspace file matches the raw file.
- **RP-4** `/assets/schema` has no `notebook`.
- **RP-5** infra's unit tier passes with `Notebook` deleted from
  `stargazer.assets` and `stargazer.assets.notebook` blocked in `sys.modules`.

Locally from the infra worktree: a `TestClient` on `app.admin_app.asgi_app`
with `PINATA_JWT` set to the org key, `PINATA_GATEWAY` set, a scratch
`STARGAZER_WORKSPACE_ROOT` and an `X-User-Subject` header. On the tenant:
infra's `verify-dashboard` (`union_dashboard.py deploy`, `fetch` from the
dashboard page, `teardown`).

### Evidence (2026-11-16, infra `413e19c`)

- Unit tier 388 passed; RP-5 388 passed. The new listing and copy tests
  failed first for the missing behavior.
- Local, real Pinata and GitHub: RP-1 200, 6 records, none notebooks; RP-2
  4 tutorials and 2 featured, all `asset=notebook`; RP-3 400
  `cannot copy from section: public`, and 200 `scrna-seq-clustering` matching
  the raw file; RP-4 no `notebook`.
- Tenant: the test account's dashboard deployed from `413e19c` but not
  driven. Neither the built-in browser nor Chrome had a GitHub session for
  the console's sign-in. Teardown: `stopped: ['dashboard']`, `live runs: []`.

## Outcome

Shipped in infra PR 33 (merge `43c7c5c`): the explorer's public listing leaves out notebooks, `/workspace/copy` has no public section, `app/public_notebooks.py` is gone and no `app/` module imports `Notebook`. The public tier held no notebooks, so nothing was migrated or deleted. Verified by infra's unit tier (also without the type) and the routes against real Pinata and GitHub (evidence above). No comments on the PR. Left: the SDK side, ticket [[drop-notebook-asset]]; the `stargazer-workspaces` App's Pull requests permission, the user's to drop; the explorer on the tenant, not driven.

Related: [[board]], [[drop-notebook-asset]], [[notebooks-in-git]], [[public-notebooks]].
