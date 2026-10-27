---
title: Public notebooks
status: backlog
priority: normal
created: 2026-10-16
---

A notebook in a user's workspace is a plain file (ticket
`save-whole-workspace`). It becomes an asset when it's published (decided
2026-10-17). A Publish button on a workspace notebook's tile puts it on
Pinata's public network as a `Notebook` asset, with its CID and keyvalues.
The dashboard then lists public notebooks next to the user's own. Opening a
public notebook for editing copies it into the user's workspace, where it's
saved like any other file.

**The `Notebook` asset type** lives in `src/stargazer/assets/notebook.py`,
with `_asset_key = "notebook"` and the fields `title`, `description` and
`slug`. `title` and `description` come from the setup block's `main_name`
and `main_description` (`app/notebook_meta.py`), and `slug` is the workspace
filename's stem, which ties the public record to the notebook it came from.
With `_owner` that's five keyvalues, under Pinata's nine. Nothing else
creates one.

**Publishing goes through the dashboard**, not `StorageClient.publish(cid)`:
that publishes a stored asset by its index row, and a workspace notebook has
no row. The dashboard uploads the file straight to the public tier, stamped
with the user's `_owner`. A `main_description` over Pinata's 250-character
value limit is refused with the existing message, before anything is sent.

## Decisions (2026-10-26)

- **Publishing again replaces.** Publishing a notebook that's already public
  removes the user's earlier public record with the same `slug` from Pinata,
  so the listing has one entry per notebook. People who copied the earlier
  version keep their copy.
- **Unpublish is in scope.** A published notebook's tile has Unpublish, which
  deletes the user's public record with that `slug` from Pinata. Only the
  owner's dashboard offers it, and the route refuses a record whose `_owner`
  isn't the user.
- **The public switch applies.** With `STARGAZER_PUBLIC_ASSETS=off` (ticket
  `turn-off-public-assets`), the dashboard hides Publish, Unpublish and the
  public notebooks section, and their routes answer 503 like the other public
  routes.

## Notebooks in the repo

**They aren't published** (decided 2026-10-17, replacing the 2026-10-16 plan
to publish the tutorials and the scRNA notebook). GitHub already makes them
public. The tutorials stay in the SDK and the dashboard's Tutorials section,
and the scRNA notebook stays in the SDK and the Workflows section (moving it
to a top-level `notebooks/` folder, ticket `top-level-notebooks`, is shelved
as of 2026-10-21). Publish is for workspace notebooks only.

## Reading the public tier

Hosted dashboards have the Pinata key as a secret (ticket
`dashboard-pinata-key`, merged as #40), so they can read Pinata's public
index. Union injects app secrets without putting the value in the app record
(measured 2026-10-17).

## The dashboard's asset browser

Once notebooks are stored as `asset=notebook` rows, the asset browser on the
dashboard's home page leaves them out, since notebooks have their own
sections there. Test it: a notebook row in the index isn't in the browser's
listing. Carried over from ticket `assets-on-dashboard-home`.
