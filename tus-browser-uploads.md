---
title: TUS resumable uploads, browser half
status: backlog
priority: low
created: 2026-06-10
---

Pinata's plain multipart POST is hard-capped at 100MB; larger files need the TUS
resumable endpoint (per-file ceiling then 10 GiB, chunks <50MB).

- [x] **SDK/task outputs (2026-06-10):** `PinataClient.upload()` now
      size-branches — ≤100MB plain POST, larger streams via chunked TUS
      (`_upload_tus`, CID read from the `Upload-Cid` header on the final
      PATCH). Chunked-first: no resume yet. Verified by
      `test_tus_upload_multichunk_roundtrip` (pinata-marked).
- [ ] **Browser/assets page:** wire `tus-js-client` into `assets.html`
      (Piece 3 territory) so the page lifts past `MAX_UPLOAD_BYTES` (100MB).
      Confirmed empirically that **signed upload URLs speak full TUS** —
      anonymous TUS creation against a signed URL returns 201 with a signed,
      resumable Location URL whose mint-time keyvalues/filename/network/size
      cap ride in signature-protected query params, so the
      no-unvalidated-metadata property carries over. Note: the resumable
      session inherits the signed URL's `expires`, so mint generously for
      big files.
- [ ] **Resume** (`HEAD`-then-continue-from-offset) for both halves — the
      real payoff of TUS (survive a dropped multi-GB upload); deferred until
      a flaky large upload demands it.

Putting the asset-manager page on the index ([asset-manager-on-index](asset-manager-on-index.md)) retires most of the browser half.
