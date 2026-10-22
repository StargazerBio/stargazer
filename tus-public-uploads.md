---
title: Public uploads over TUS, up to 10 GB
status: doing
priority: normal
created: 2026-10-21
---

The Pinata half of ticket `tus-browser-uploads`, split out when its store
half went to review as PR #72. Public uploads from the asset page still use a
Pinata signed URL, capped at 100 MB.

- [x] A public upload's `POST /assets/tus` creates a Pinata TUS upload, each
      `PATCH` is passed on to it as one `PATCH`, and Pinata's CID has to equal
      `CidBuilder`'s, as `StorageClient.publish` checks.
- [x] The form sends public uploads to `/assets/tus` too, and `/assets/sign`
      and the browser→Pinata upload go.
- [x] Tests against a fake Pinata TUS endpoint: three chunks passed on in
      order, and a CID mismatch → an error and no record kept.
- [x] Docs: the upload path in `docs/architecture/app.md` and
      `app_internals.md`, and the public limit on the form.
- [x] Verify on Union with the test account: upload a public file over
      100 MB, see its CID in the Public tab, then delete it from Pinata.
      Publishing puts the file on the public network, so confirm with the
      user before running it.

## Verification

On branch `feat/tus-public-uploads`:

- Unit tier: 517 passed. New in `tests/unit/test_assets_routes.py`
  (`TestTusPublic`): three chunks passed on to a fake Pinata TUS upload in
  order, with the uploader stamped as `_owner`; a CID mismatch → 422, the
  Pinata file deleted, and the upload gone; ten keyvalues → 422 before
  Pinata; another user's `HEAD`/`PATCH` → 403; a piece over
  `TUS_CHUNK_BYTES` → 413. Anonymous → 401 and public off → 503 on creation.
- Pinata tier (`test_client.py`, `test_cid_drift.py`): 13 passed, including
  the multi-chunk roundtrip and the >100 MB drift check, both on
  `_upload_tus` now running on `tus_create`/`tus_patch`.
- Union, 2026-10-21, the test account's dashboard deployed from 7591c37 and
  driven in Chrome: a 150 MiB public upload through the form finished in
  ~45 s; the page's CID, the Public tab's record and `compute_cid` of the
  same bytes all `bafybeiakwauhpou45iceifmplyjqmla3anxe4dt3lkgnjka4r26c7vwefu`;
  the row showed green as the user's own. Then deleted from Pinata
  (`query` empty, `get` None) and every app in `u-pryce` stopped.
