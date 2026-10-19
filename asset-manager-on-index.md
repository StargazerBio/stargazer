---
title: The asset page's Private tab on the user's index and store
status: done
priority: high
created: 2026-10-06
pr: 42
---

**The asset page's Private tab moves onto the user's own index and store.**
Afterwards it lists, uploads, downloads and edits the same assets the user's
tasks write, on every dashboard. This is the first step of making the
dashboard an asset explorer and notebook launcher (decided 2026-10-16); the
second, moving the browser onto the dashboard's home page, is ticket
`assets-on-dashboard-home`.

Point the asset-manager page at the user's index instead of Pinata. A follow-up from [plan 27](archive/27_asset_storage_index.md),
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
| Private tab | None: the page is public-only (ticket `dashboard-pinata-key`) | On, on every dashboard |
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
      ephemeral-storage limit before raising it. Ticket
      `tus-browser-uploads` takes private uploads past 100 MB, up to 10 GB,
      without the disk.

## The Private tab on the index and store

The dashboard already owns the index (`_get_index()` in `app/index_api.py`),
and its pod role can read and write the store (Litestream does). The page's
routes switch from Pinata to those two for `network=private`;
`network=public` stays on Pinata.

Branch `feat/asset-manager-on-index`.

- [x] Tests first, in `tests/unit/test_assets_routes.py`, against a real
      `SqliteIndex` and a temp-dir store through FastAPI's `TestClient`
      (all twelve failed first, for the missing behavior): upload then list
      with the stored file and the CID `compute_cid` gives; a keyvalue
      filter; download returns the bytes; an unknown CID 404s; an update
      merges and restamps `_owner`; bad keyvalues 400 with nothing written;
      over the cap 413 with nothing written; another signed-in user 403 on
      every private route; anonymous 401; private works without a Pinata
      key while public 503s; and the page's tabs and upload choices with
      and without a key.
- [x] `POST /assets/upload?filename=&keyvalues=`: keyvalues checked with
      `build_asset()` before the body is read, the body streamed to a temp
      file (413 past `MAX_UPLOAD_BYTES`), then `StorageClient.upload` on the
      dashboard's index, with its cache in the same temp dir so nothing
      outlives the request. Raw body, not a multipart form.
- [x] `GET /assets/list?network=private`: `index.query(params)`.
- [x] `GET /assets/download/{cid}?network=private`: **streamed through the
      dashboard** (`flyte.storage.get_stream`), not a presigned redirect.
      One code path for a local store and the bucket, using only the read
      the pod's role already has; presigning with the pod's credentials was
      never tried.
- [x] `POST /assets/update` for private records: `index.merge(cid, patch)`,
      with `_owner` restamped.
- [x] Owner gate on the private routes: the signed-in subject must equal
      `SG_OWNER_SUBJECT`. Locally, with no owner set, allow.
- [x] Drop Pinata's private network from the client: `PinataClient` loses
      `network` (every call is on `NETWORK`, "public") and
      `_get_signed_url`. Pinata tier: 12 passed against the real API.
- [x] The Private tab is back, the default for a signed-in user. The page
      no longer needs a Pinata key: without one the Public tab says shared
      data isn't available and the upload form offers Private only.

## Verify

- [x] On the test account's Union dashboard (2026-10-18, deployed from
      `311c7da`):
  - As the org admin, not the dashboard's owner: private list, download
    and upload → 403, "Only this dashboard's owner can reach its private
    assets."; public list → 200.
  - In Chrome as the test account: the page opened on the Private tab and
    listed the account's stored assets (the scRNA task outputs, earlier
    verification notes, the 150 MB `big2.bin`). A custom `devbox_probe`
    upload with a unique tag from the form → "Uploaded ✓", stored at
    `.../users/387300641116005877/assets/bafkreiaawxkqbjckqcrlh5srgt6jyee37ib4qzx6lcbg5lw7dfkw7dsbyi/probe_ami-mvd9pj34_0.txt`
    with `_owner` stamped. The download → 200 with the same bytes. A
    metadata edit → merged, owner kept, shown in the listing.
  - `tests/devbox/pod_tasks.consume(tag="ami-mvd9pj34")` in `u-pryce`,
    pointed at the dashboard's in-cluster index (run
    `u2n8wv4s5dhl8fzncf4k`) → `['ami-mvd9pj34:0']`: a task pod found the
    file through `assemble()` and read it.
  - Torn down: the dashboard stopped, nothing active or running in
    `u-pryce` or `flytesnacks`. The probe file stays in the test account's
    store.

## Docs

- [x] `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md`: the Private tab's
      data path. `docs/architecture/configuration.md`: the client's
      `network` argument is gone.
- [x] `src/stargazer/utils/pinata.py` docstrings: no private network left.

## Follow-ups (not in this ticket)

- Private uploads up to 10 GB, resumable, passed through the dashboard to
  the store in chunks: ticket `tus-browser-uploads`. It replaces the earlier
  idea of a presigned `PUT` straight from the browser, which needed a CORS
  rule on the bucket.

## Outcome

Merged in #42 (2026-10-18). The asset page's Private tab is the dashboard
owner's own index and store, the same ones their tasks write to: listing,
upload streamed through the dashboard into the store, download streamed
back, and metadata edits on the index row. Only the owner reaches it;
anyone else signed in gets a 403. The Public tab is Pinata's public network.
`PinataClient` lost its private network. Private downloads stream through
the dashboard rather than redirecting to a presigned URL, so one path serves
a local store and the bucket.

Verified on the test account's dashboard (above): a non-owner gets 403, and
upload, download with the same bytes, and a metadata edit all work in
Chrome. A task pod found the uploaded file through `assemble()`. Pinata tier
12 of 12.

Left: private uploads stay capped at 100 MB until ticket
`tus-browser-uploads` (Q1 here). The dashboard's home page as an asset
explorer is ticket `assets-on-dashboard-home`.
