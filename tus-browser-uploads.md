---
title: Resumable uploads up to 10 GB from the asset page
status: backlog
priority: normal
created: 2026-06-10
blocked_by:
  - asset-manager-on-index
  - dashboard-pinata-key
---

Uploading a file from your machine goes up to 10 GB, private or public, and
a dropped upload picks up where it stopped (decided 2026-10-17). The browser
sends every upload in chunks over the TUS resumable-upload protocol, and the
dashboard decides where it goes:

- **Private:** to the dashboard, which passes each chunk on to the user's
  store as one part of a multipart upload, and works out the CID as the
  chunks go by.
- **Public:** to a signed Pinata upload URL that the dashboard mints, as
  public uploads do today. The bytes go straight to Pinata, and Pinata works
  out the CID.

## Why

- **The asset page's upload is capped at 100 MB** (`MAX_UPLOAD_BYTES` in
  `app/assets.py`). The cap is Pinata's: today the browser uploads to Pinata
  through a signed URL, and that takes only Pinata's plain upload, which stops
  at 100 MB. Ticket `asset-manager-on-index` moves private uploads to browser
  → dashboard → store, and keeps 100 MB to start, because the dashboard has
  512 Mi–1 Gi of memory and no declared disk.
- **Pinata takes up to 10 GiB over TUS,** and signed upload URLs speak full
  TUS (measured 2026-06-10): creating an upload against a signed URL returns
  a signed, resumable upload URL, with the keyvalues, filename, network and
  size cap from minting inside the signature. Hosted dashboards can mint them
  once they have the key (ticket `dashboard-pinata-key`).
- **The browser can't upload straight to the bucket.** It has no CORS rule
  (measured 2026-10-07, in `asset-manager-on-index`). Going through the
  dashboard needs none.
- **A big file already in a notebook's workspace doesn't need this.** The
  pod uploads it itself (ticket `save-whole-workspace`).

## Design

- **Client.** `tus-js-client`, pinned, from a CDN, in the upload form. Only
  the endpoint differs: `/assets/tus` for a private upload, a signed URL for
  a public one. It sends 48 MB chunks, which fit every limit: S3 needs at
  least 5 MB per part except the last, Pinata takes under 50 MB, and one
  chunk at a time fits the dashboard's memory.
- **Public uploads** mint the signed URL as `/assets/sign` does now, with
  the size cap raised to 10 GB. A resumable upload expires with the signed
  URL it was created from, so the expiry has to cover a slow 10 GB upload.
- **Private uploads: the server.** The core TUS protocol on the dashboard,
  under `/assets/tus`.
  `POST` creates an upload from `Upload-Length` and `Upload-Metadata` (the
  filename and the keyvalues), `HEAD` reports how much has arrived, and
  `PATCH` appends at that offset. The keyvalues are checked with
  `build_asset()` when the upload is created, so a bad one fails before any
  bytes move. The same owner gate as the other private routes.
  `Upload-Length` over 10 GB → 413. A `PATCH` at the wrong offset → 409, as
  the protocol says.
- **Each `PATCH` is one part of an S3 multipart upload,** written through
  obstore's writer (`obstore.open_writer_async`, in the installed 0.11.1).
  The file never touches the dashboard's disk.
- **The CID is computed as the chunks pass.** It's the UnixFS DAG in
  `src/stargazer/utils/cid.py`: 256 KiB raw leaves under a balanced tree. So
  the leaves are hashed as the bytes arrive, and the tree is built from them
  at the end. 10 GB is about 41,000 leaves, a few megabytes of state.
  `compute_cid` becomes a wrapper over the same incremental builder, so
  there's still one implementation of an asset's identity.
- **Upload state lives in the dashboard's memory:** the writer, the offset,
  and the CID builder. A dropped connection resumes while the dashboard pod
  is up. The dashboard is one replica (`Scaling(replicas=(0, 1))` in
  `app/admin_app.py`), and it stays up while requests are arriving (inferred
  from how Knative scales). If the dashboard restarts mid-upload, the upload
  starts again from zero. Keeping state across restarts can come later, if
  it's needed.
- **Where the bytes land:** where they were uploaded, and the index row's
  `uri` points there (Q1, decided 2026-10-18). The upload goes to
  `users/<owner>/uploads/<upload id>/<name>`, so a crash leaves nothing at a
  path that looks like a stored asset. If the CID is already in the user's
  index when the last chunk arrives, the upload is deleted and the existing
  row stays as it is.
- **`StorageClient.upload` checks the row before the path.** Today it skips
  the transfer when a file exists at the CID path. With uploads elsewhere,
  the same bytes uploaded again from the SDK would be stored a second time
  and the row repointed, leaving the first copy unreferenced. It skips the
  transfer when the CID already has a row whose `uri` exists instead.
- **Abandoned uploads.** An unfinished multipart upload keeps its parts, and
  they're billed, until it's aborted. Today nothing can abort one: the bucket
  has no rule for it, and the pods' role isn't allowed to (Q2). How they get
  cleaned up is Q3.

## Open questions

- [x] **Q1. Where the file lands.** A stored file's path contains its CID
      (`users/<owner>/assets/<cid>/<name>`), which is only known after the
      last chunk. Decided 2026-10-18: leave the bytes where they were
      uploaded and point the index row's `uri` there. Copying to the CID
      path would need a multipart copy above 5 GB, and computing the CID in
      the browser is a second implementation that has to match bit for bit.
      A search on 2026-10-18 found one place that builds the path,
      `StorageClient.upload` (`src/stargazer/utils/storage.py`), and every
      reader going through the row: `StorageClient.download` and `delete`,
      and the asset page's private download (ticket
      `asset-manager-on-index`).
- [x] **Q2. Does the tenant bucket abort unfinished multipart uploads?**
      No (measured 2026-10-18 with the read-only AWS access):
  - The bucket's one lifecycle rule is `items_non_current_versions_expiration`:
    versioning is on, and a deleted or overwritten object's old version is
    kept for 7 days. There's no `AbortIncompleteMultipartUpload` rule, and
    no bucket policy.
  - The pods' role (`union-us-west-2-stargazerbio-userflyterole`) has
    `s3:GetObject*`, `s3:PutObject*`, `s3:DeleteObject*` and `s3:ListBucket`
    on the bucket. IAM's policy simulator: `s3:PutObject` allowed, so
    starting, uploading parts and completing work; `s3:AbortMultipartUpload`,
    `s3:ListMultipartUploadParts` and `s3:ListBucketMultipartUploads`
    `implicitDeny`.
  - No unfinished multipart uploads in the bucket.
  
  So an upload abandoned partway, by a closed browser or a dashboard
  restart, stays in the bucket and is billed indefinitely. Nothing
  Stargazer runs can find it or remove it. The same goes for any large
  `flyte.storage.put` that fails partway today (inferred: the store's
  client uploads big files in parts).
- [ ] **Q3. How abandoned uploads get cleaned up.** Union manages the
      bucket and the role, so either fix is a request to them. Options:
  - **A lifecycle rule** on `union-us-west-2-stargazerbio`:
    `AbortIncompleteMultipartUpload` with `DaysAfterInitiation: 1`, for the
    whole bucket. It catches every leftover, a crash's included, and today's
    large writes too. Nothing in the dashboard changes.
  - **Abort permissions** for the role (`s3:AbortMultipartUpload`,
    `s3:ListBucketMultipartUploads`), so the dashboard aborts idle uploads
    and, at startup, any left under `uploads/`. That's more code, and it
    still misses anything a sweep doesn't reach.
  - **No multipart while uploading:** each chunk is stored as its own object
    under `uploads/<id>/`, which the role can delete. At the end the chunks
    are joined in the bucket with a short multipart copy, and the chunk
    objects are deleted. Resumes survive a dashboard restart. A crash in the
    seconds the copy takes still leaves an upload nothing can abort.

  Recommendation: ask Union for the lifecycle rule. It's one setting and
  covers every case.

## Pieces

- [ ] An incremental CID builder in `src/stargazer/utils/cid.py`: its own
      ticket, `incremental-cid` (split out 2026-10-18).
- [ ] `StorageClient.upload` skips the transfer when the CID has a row
      whose `uri` exists. A test in `tests/utils/test_storage.py`: a row
      pointing at a file outside the CID path, then `upload` of the same
      bytes → nothing written at the CID path, and the row's `uri`
      unchanged.
- [ ] The TUS routes. Tests in `tests/unit/test_assets_routes.py`, against a
      `file://` store in a temp dir and a `SqliteIndex`:
  - create, then three `PATCH`es → an index row whose CID is
    `compute_cid` of the file, and a download returns the same bytes
  - the same file uploaded twice → one row, and the second upload's bytes
    are deleted
  - `HEAD` after the first chunk → its offset, and finishing from there
    gives the same CID
  - a `PATCH` at the wrong offset → 409
  - `Upload-Length` over 10 GB → 413; bad keyvalues → 422, with nothing
    written
  - a signed-in user who isn't the owner → 403; anonymous → 401
  - an upload idle past its timeout → aborted, and a `PATCH` to it → 404
- [ ] Public signing: `/assets/sign` accepts up to 10 GB. Tests: a 5 GB
      size → a signed URL whose size cap is 10 GB and whose expiry is the
      long one; over 10 GB → 413.
- [ ] The upload form sends every upload with `tus-js-client`, to the
      dashboard or to the signed URL, and shows a 10 GB limit.
- [ ] Docs: `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md` (the upload path),
      and the upload limit in the user guides, in product terms.
- [ ] Verify on Union with the test account's dashboard:
  - upload a private file over 5 GB from the asset page, take the browser
    offline partway (devtools), bring it back, and see it resume
  - upload a public file over 100 MB, see its CID in the Public tab, then
    delete it from Pinata
  - the row's CID matches `compute_cid` run locally on the same file
  - `assemble()` finds it from a task pod
  - no unfinished multipart uploads are left (`list-multipart-uploads`)
  - measure the upload time and the dashboard's memory during it, and check
    that Union's ingress takes 48 MB requests

  Then stop every app the check started.

## Already done

- **2026-06-10:** `PinataClient.upload()` sends files over 100 MB to
  Pinata's TUS endpoint in chunks, up to Pinata's 10 GiB, for the SDK and
  task outputs. Verified by `test_tus_upload_multichunk_roundtrip` (pinata
  tier).
