---
title: Public notebooks
status: doing
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

## Plan

- [ ] `Notebook` asset (`src/stargazer/assets/notebook.py`), exported from `stargazer.assets`
- [ ] Publish (`POST /workspace/publish`): upload the workspace file to the public tier through the existing TUS methods of `PinataClient`, stamped with the dashboard owner's `_owner`; then delete the owner's earlier records with the same `slug`
- [ ] Unpublish (`POST /workspace/unpublish`): delete the owner's records with that `slug`; another user's are never touched
- [ ] Public notebooks section on the dashboard; Copy to workspace goes through `/workspace/copy` with `section=public`
- [ ] Asset browser leaves out `asset=notebook` (listing and the upload form's types)
- [ ] `STARGAZER_PUBLIC_ASSETS=off`: no Publish/Unpublish/section, routes 503
- [ ] Docs (`app.md`, `types.md`, `catalog.md`, `app_internals.md`)
- [ ] Verified on Union with one probe notebook, nothing left published

Choices:
- Pinata stores identical bytes once per account and keeps the first upload's keyvalues (measured 2026-10-26: three uploads of one file, two owners, one record with the first's keyvalues). So publishing bytes that are already public under someone else's record, or under another of the owner's slugs, is refused with a 409, and nothing is deleted.
- The record's `_owner` is the dashboard's owner (the notebook's), not an admin visitor.
- A public tile's button is "Copy to workspace", like a workflow's; a name that's taken is a 409, as for any copy.

## Verification recipe: Public notebooks

A dashboard user publishes a workspace notebook from its tile, sees it in the
Public notebooks section, republishes an edit (still one public record),
copies a public notebook into their workspace, and unpublishes it.

### Sub-features

- `pn-publish`: Publish puts the notebook on Pinata's public network as an
  `asset=notebook` record with `title`, `description`, `slug` and the owner's
  `_owner`, and the Public notebooks section shows it.
- `pn-republish`: after an edit, Republish leaves exactly one public record
  for the slug, the new CID, and the old CID is gone from Pinata.
- `pn-copy`: Copy to workspace on the public tile writes a workspace notebook
  with the published bytes.
- `pn-unpublish`: Unpublish removes the record from Pinata and from the section.

### How to get to it (user POV)

- Dashboard → Workspace → a notebook tile's **Publish** / **Republish** /
  **Unpublish**; Dashboard → **Public notebooks** → **Copy to workspace**.

### Driving it

Preconditions: the `verify-stargazer` Union tenant preconditions; the
built-in browser pane signed in to the console as the test account.

- **Deploy.** With infra's `tenant.env` exported, `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy`. Open the printed URL from the console page with `location.href`.
- **Probe notebook.** Create a Blank notebook named `pn-probe-<date>`; in its gear, set `main_description = "Public notebooks probe"`.
- **Publish (`pn-publish`).** Click **Publish**, accept the confirm. After the reload the tile shows Republish + Unpublish, and the section has a `pn-probe-<date>` tile. From this checkout, `PinataClient().query({"asset": "notebook", "slug": "pn-probe-<date>"})` returns one record with the test account's subject as `_owner`.
- **Republish (`pn-republish`).** Change the description in the gear, click **Republish**. The query returns one record with the new CID; `PinataClient().get(<old cid>)` is None.
- **Copy (`pn-copy`).** Delete the probe workspace tile (the public record stays), then **Copy to workspace** on its public tile: the workspace tile comes back, and `/workspace/download?slug=pn-probe-<date>` returns the published bytes.
- **Unpublish (`pn-unpublish`).** Click **Unpublish**: the section no longer lists it, and the query returns `[]`.
- **Teardown.** Delete the probe tile, `union_dashboard.py teardown`: `live runs: []`. The query returns `[]`.

### Gotchas

- Pinata stores identical bytes once per account, keeping the first
  upload's keyvalues, so a probe whose bytes match an earlier public file
  is refused with 409. Give the probe a name nobody has published.
