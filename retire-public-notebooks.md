---
title: retire-public-notebooks
status: next
priority: normal
created: 2026-11-03
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

Related: [[board]], [[notebooks-in-git]], [[public-notebooks]].
