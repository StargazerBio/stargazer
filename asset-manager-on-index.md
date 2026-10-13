---
title: Asset-manager page on the index
status: backlog
priority: normal
created: 2026-10-06
---

Point the asset-manager page at the user's index instead of Pinata. That also retires most of
[tus-browser-uploads](tus-browser-uploads.md). A follow-up from [plan 27](archive/27_asset_storage_index.md),
which moved task outputs onto the object store and the asset index into each user's dashboard.

**The asset manager's Private tab moves onto the user's index and store.** It
is the last thing still using Pinata's private network. Afterwards the tab
lists, uploads, downloads and edits the same assets the user's tasks write,
and it works on hosted dashboards, which carry no Pinata key.

**A bucket per user is out of scope** (decided 2026-10-08). Every user's data
lives under `users/<subject>/` in the shared tenant bucket, and the dashboard
and upload form tell users not to upload sensitive data
([alpha-notice](alpha-notice.md)). Hardening that is
[per-user-storage-isolation](per-user-storage-isolation.md).

## Why

- **Pinata is the public tier only** (decided in plan 27's review). The
  Private tab still uploads to, lists, and signs downloads from Pinata's
  private network. It contradicts that decision, and it is off on hosted
  dashboards because a dashboard can't hold a Pinata key.
- **Any pod can read every user's files, and that's accepted for now.** Every
  project on the tenant runs as one role,
  `union-us-west-2-stargazerbio-userflyterole`, which reaches the whole tenant
  bucket (measured in [plan 25](archive/25_workspace_state_object_storage.md);
  `.opencode/reference/architecture/app_internals.md` on `main`). The
  `users/<subject>/` prefixes are a convention, not a boundary. The alpha
  notice is what covers this until isolation is hardened.

## What changes

| | Today | After |
|---|---|---|
| Private tab listing | Pinata private network, filtered by `_owner` | The dashboard's own index |
| Private upload | Browser → Pinata through a signed URL, 100 MB cap | Browser → dashboard → the user's store |
| Private download | Pinata signed URL | A presigned store URL, or the file itself when run locally |
| Metadata edits | Pinata | The index (`merge`) |
| Private tab on hosted dashboards | Off (no Pinata key) | On |
| Pinata's private network | Used by the Private tab | Unused; `PinataClient` loses `network` |

## Verified (2026-10-07)

Measured unless marked otherwise.

- **The tenant bucket has no CORS rule.** A browser preflight for `PUT` to
  `union-us-west-2-stargazerbio` returns 403, "CORS is not enabled for this
  bucket". A browser can't upload straight to the shared bucket, so uploads go
  through the dashboard.
- **Signing and streaming are already installed.** `obstore.sign_async` (the
  store library under `flyte.storage`) and `flyte.storage.put_stream` import
  in the project env. Not tried yet: presigning with a pod's web-identity
  credentials.
- **The dashboard has 512 Mi–1 Gi of memory and no declared disk**
  (`app/admin_app.py`), so an upload through it has to stream to disk, not
  memory.

## Open questions

- [ ] **Q1. Upload size through the dashboard.** Uploads stream to the pod's
      ephemeral disk. Start at the current 100 MB cap and confirm the pod's
      ephemeral-storage limit before raising it.

## The Private tab on the index and store

The dashboard already owns the index (`_get_index()` in `app/index_api.py`),
and its pod role can read and write the store (Litestream does). The page's
routes switch from Pinata to those two for `network=private`;
`network=public` stays on Pinata.

- [ ] Tests first, in `tests/unit/test_assets_routes.py`, against a
      `SqliteIndex` and a `file://` store in a temp dir through FastAPI's
      `TestClient`:
  - upload a file as the owner → listed under `network=private` with its
    keyvalues and `_owner`
  - download it → the same bytes
  - update its keyvalues → the listing shows the merge
  - a signed-in user who isn't the owner → 403 on every private route;
    anonymous → 401
  - no Pinata key → private routes still work, public routes 503
- [ ] `POST /assets/upload` for private uploads: stream the request body to a
      temp file, validate the keyvalues with `build_asset()`, stamp `_owner`,
      `StorageClient.upload(asset, tmp)` (CID, store, index row), then delete
      the temp file. Enforce the cap (Q1). The upload form posts here when
      Private is picked; Public keeps the signed Pinata URL.
- [ ] `GET /assets/list?network=private`: `index.query(params)`.
- [ ] `GET /assets/download/{cid}?network=private`: look up the row's `uri`.
      An `s3://` URI redirects to a presigned GET that expires in 5 minutes; a
      local path is served with `FileResponse`.
- [ ] `POST /assets/update` for private records: `index.merge(cid, patch)`,
      with `_owner` restamped.
- [ ] Owner gate on the private routes: the signed-in subject must equal
      `SG_OWNER_SUBJECT`. Locally, with no owner set, allow.
- [ ] Drop Pinata's private network: `PinataClient` loses `network` and
      `_get_signed_url`; `_require_pinata()` guards public routes only.
- [ ] Hosted dashboards show the Private tab. Public says shared data isn't
      available there, in product terms (no vendor or key names).
- [ ] Verify on the devbox dashboard (`cli/devbox_dashboard.py`; the
      `verify-stargazer` devbox recipe first, so storage is known good):
      upload → list → download → edit in the browser, and the uploaded file
      found by `assemble()` from a task pod. Then once on the test account's
      Union dashboard.

## Docs

- [ ] `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md`: the Private tab's
      data path.
- [ ] `src/stargazer/utils/pinata.py` docstrings: no private network left.

## Follow-ups (not in this ticket)

- Browser uploads straight to the store through a presigned `PUT`, taking the
  dashboard out of the upload path and lifting the size cap. Needs a CORS
  rule on the bucket, and the CID computed in the browser or after the
  upload. The large-upload half of [tus-browser-uploads](tus-browser-uploads.md).
