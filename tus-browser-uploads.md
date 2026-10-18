---
title: Resumable private uploads up to 10 GB through the dashboard
status: backlog
priority: normal
created: 2026-06-10
blocked_by:
  - asset-manager-on-index
---

Uploading a file from your machine as a private asset goes up to 10 GB, and
a dropped upload picks up where it stopped (decided 2026-10-17). The browser
sends the file in chunks over the TUS resumable-upload protocol to the
dashboard. The dashboard passes each chunk on to the user's store as one part
of a multipart upload, and works out the CID as the chunks go by.

## Why

- **The asset page's upload is capped at 100 MB** (`MAX_UPLOAD_BYTES` in
  `app/assets.py`). The cap is Pinata's: today the browser uploads to Pinata
  through a signed URL, and that takes only Pinata's plain upload, which stops
  at 100 MB. Ticket `asset-manager-on-index` moves private uploads to browser
  → dashboard → store, and keeps 100 MB to start, because the dashboard has
  512 Mi–1 Gi of memory and no declared disk.
- **Pinata's own TUS endpoint, which this ticket used to be about, doesn't
  help on Union.** It reaches 10 GiB, but only into Pinata, which is now the
  public tier only, and hosted dashboards hold no Pinata key.
- **The browser can't upload straight to the bucket.** It has no CORS rule
  (measured 2026-10-07, in `asset-manager-on-index`). Going through the
  dashboard needs none.
- **A big file already in a notebook's workspace doesn't need this.** The
  pod uploads it itself (ticket `save-whole-workspace`).

## Design

- **Client.** `tus-js-client`, pinned, from a CDN, in the upload form, for
  private uploads only. It sends 48 MB chunks: S3 needs at least 5 MB per
  part except the last, and one chunk at a time fits the dashboard's memory.
- **Server.** The core TUS protocol on the dashboard, under `/assets/tus`.
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
- **Where the bytes land** is Q1.
- **Abandoned uploads.** An unfinished multipart upload keeps its parts, and
  they're billed, until it's aborted. The dashboard aborts an upload idle for
  an hour, and every open one at shutdown. One left behind by a crash stays
  until a bucket lifecycle rule removes it (Q2).

## Open questions

- [ ] **Q1. Where the file lands.** A stored file's path contains its CID
      (`users/<owner>/assets/<cid>/<name>`), which is only known after the
      last chunk. Options:
  - Upload to a temporary key, then copy to the CID path. S3 copies up to
    5 GB in one call. Above that it takes a multipart copy, and whether
    obstore's `copy` does one is unchecked.
  - Leave the bytes where they were uploaded, and point the index row's
    `uri` there. If the same bytes are already stored, delete the upload and
    point at the existing file. This relies on every reader going through
    the row's `uri`, as `StorageClient.download` does. Not checked for every
    caller.
  - Compute the CID in the browser first, so the multipart upload goes
    straight to its final key, and have the dashboard check it as the bytes
    pass. That's a second implementation of the CID, in JavaScript, which
    has to match bit for bit.

  Recommendation: leave the bytes in place, once a search confirms nothing
  finds files by their path.
- [ ] **Q2. Does the tenant bucket abort unfinished multipart uploads?**
      Check its lifecycle rules with the read-only AWS access
      (`get-bucket-lifecycle-configuration`). Union manages the bucket, so
      if there's no rule, ask them for one.

## Pieces

- [ ] An incremental CID builder in `src/stargazer/utils/cid.py`, with
      `compute_cid` built on it. Tests first, in `tests/utils/test_cid.py`:
      fed in uneven chunk sizes (one byte, a prime number of bytes, 48 MB),
      it gives the CIDs the existing tests already pin, which Pinata
      assigned: the empty file, one leaf, two levels, and three levels.
- [ ] The TUS routes. Tests in `tests/unit/test_assets_routes.py`, against a
      `file://` store in a temp dir and a `SqliteIndex`:
  - create, then three `PATCH`es → an index row whose CID is
    `compute_cid` of the file, and a download returns the same bytes
  - `HEAD` after the first chunk → its offset, and finishing from there
    gives the same CID
  - a `PATCH` at the wrong offset → 409
  - `Upload-Length` over 10 GB → 413; bad keyvalues → 422, with nothing
    written
  - a signed-in user who isn't the owner → 403; anonymous → 401
  - an upload idle past its timeout → aborted, and a `PATCH` to it → 404
- [ ] The upload form sends private uploads with `tus-js-client`. The form
      shows 10 GB for private uploads and 100 MB for public ones.
- [ ] Docs: `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md` (the upload path),
      and the upload limit in the user guides, in product terms.
- [ ] Verify on Union with the test account's dashboard:
  - upload a file over 5 GB from the asset page, take the browser offline
    partway (devtools), bring it back, and see it resume
  - the row's CID matches `compute_cid` run locally on the same file
  - `assemble()` finds it from a task pod
  - no unfinished multipart uploads are left (`list-multipart-uploads`)
  - measure the upload time and the dashboard's memory during it, and check
    that Union's ingress takes 48 MB requests

  Then stop every app the check started.

## Already done, or not planned

- **Done 2026-06-10:** `PinataClient.upload()` sends files over 100 MB to
  Pinata's TUS endpoint in chunks, up to Pinata's 10 GiB, for the SDK and
  task outputs. Verified by `test_tus_upload_multichunk_roundtrip` (pinata
  tier).
- **Not planned:** public uploads from the asset page past 100 MB. Signed
  upload URLs do speak TUS (measured 2026-06-10), so `tus-js-client` against
  a signed URL would work. But only a dashboard with a Pinata key has public
  uploads, and hosted ones don't.
