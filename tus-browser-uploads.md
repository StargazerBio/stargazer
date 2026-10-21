---
title: Resumable uploads up to 10 GB from the asset page
status: backlog
priority: normal
created: 2026-06-10
blocked_by:
  - union-console-handoff
---

Uploading a file from your machine goes up to 10 GB, private or public, and
a dropped upload picks up where it stopped (decided 2026-10-17). The browser
sends every upload, private or public, in chunks over the TUS
resumable-upload protocol to the dashboard, which works out the CID as the
chunks go by and passes each one on to a backend (decided 2026-10-18):

- **Private:** the user's store, each chunk one part of a multipart upload.
- **Public:** Pinata, each chunk one `PATCH` of a Pinata TUS upload.

One path from the client to the dashboard, and backends added behind it as
they're needed. The store backend comes first; public uploads keep today's
100 MB signed-URL path until the Pinata backend replaces it.

Waits on ticket `assets-on-dashboard-home` (decided 2026-10-18): that moves
the upload form onto the dashboard's home page, and this rewrites it, so
this goes second.

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
  (measured 2026-10-07, in `asset-manager-on-index`, and again 2026-10-18).
  Going through the dashboard needs none.
- **Direct to the bucket was considered and not taken** (2026-10-18): a CORS
  rule we'd add ourselves, part URLs the dashboard signs, and the CID worked
  out by reading the file back. It's a second client path, and it only works
  for S3 stores. Everything through the dashboard is one client path, with
  the backends behind it.
- **A big file already in a notebook's workspace doesn't need this.** The
  pod uploads it itself (ticket `save-whole-workspace`).

## Design

- **Client.** `tus-js-client`, pinned, from a CDN, in the upload form. One
  endpoint, `/assets/tus`, for both networks; the network rides in
  `Upload-Metadata`. It sends 48 MB chunks, which fit every limit: S3 needs
  at least 5 MB per part except the last, Pinata takes under 50 MB, and one
  chunk at a time fits the dashboard's memory.
- **The server.** The core TUS protocol on the dashboard, under
  `/assets/tus`.
  `POST` creates an upload from `Upload-Length` and `Upload-Metadata` (the
  filename, the network and the keyvalues), `HEAD` reports how much has arrived, and
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
- [ ] **Q3. How abandoned uploads get cleaned up.** Set aside for now
      (decided 2026-10-18): the buckets held no unfinished uploads when
      checked that day, so the rule is preventive. Revisit before TUS
      uploads ship. Union manages the
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

  - **The lifecycle rule, set by us.** The AWS account is ours, so its admin
    can add the rule without Union. The catch: Union's Terraform owns the
    bucket's lifecycle. CloudTrail shows `union-ai-admin` creating the bucket
    and setting its versioning and lifecycle with Terraform on 2026-09-29,
    with no lifecycle change since. A re-apply of their Terraform would put
    their configuration back and drop ours (inferred from how Terraform
    treats a lifecycle configuration). `put-bucket-lifecycle-configuration`
    replaces every rule, so the existing one has to be sent with it.

  Recommendation: set the rule ourselves, check it's still there with the
  read-only access after Union touches the dataplane, and tell Union so
  their Terraform keeps it. 1 day also bounds how long a paused TUS upload
  can be resumed.

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
- [ ] The upload form sends private uploads with `tus-js-client` to
      `/assets/tus`, and shows a 10 GB limit for them.
- [ ] The Pinata backend: a public upload's `POST` creates a Pinata TUS
      upload, each chunk is passed on as a `PATCH`, and Pinata's CID has to
      equal the builder's, as `StorageClient.publish` checks. Then the form
      sends public uploads to `/assets/tus` too, and `/assets/sign` and the
      browser→Pinata upload go. Tests against a fake Pinata TUS endpoint:
      three chunks passed on in order, a CID mismatch → an error and no
      record kept.
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
