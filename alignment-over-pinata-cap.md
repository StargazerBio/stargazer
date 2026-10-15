---
title: Alignment can't be uploaded to Pinata
status: doing
priority: normal
created: 2026-10-13
---

Pinata refuses a new file with more than 9 keyvalues, `_owner` included.
`Alignment` declares 8 fields (`sample_id`, `format`, `sorted`,
`duplicates_marked`, `bqsr_applied`, `tool`, `reference_cid`, `r1_cid`), so
its keyvalues are 9 with `asset`, and 10 once `_owner` is stamped. No
`Alignment` can be published to the public tier.

**Evidence.** Measured 2026-10-13 against the real API, with probe files of
9 and 10 keys (not with an actual `Alignment`): 9 are stored, 10 are refused.
That `Alignment` is 9 keys before `_owner` is counted from the registry. On
`main` the failure looks like this:

- Asset page, public upload of an `alignment`: `/assets/sign` stamps `_owner`
  and mints the URL; the browser upload then fails with
  `400 "Failed to parse keyvalues as JSON"`.
- `PinataClient.upload()` with `STARGAZER_OWNER` set: `400 Bad Request`, the
  body (Pinata's "maximum of 9 key values") dropped by `raise_for_status()`.

Once ticket `open-asset-keyvalues` merges, both paths raise first with "Public
assets can carry at most 9 metadata fields, counting the asset type and owner;
this one has 10." The message is clearer, but the upload still can't happen.

**Options** (the choice is the user's):

- Drop or merge declared fields on `Alignment`. `format` is derivable from the
  file name, and `sorted` from the BAM header. Every field dropped also leaves
  one key for extras on the public tier.
- Don't stamp `_owner` as a keyvalue on Pinata, and attribute some other way.
  This touches every type and the asset page's ownership checks.
- Ask Pinata for a higher cap. Their error message invites it.
