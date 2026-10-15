---
title: Alignment can't be uploaded to Pinata
status: done
priority: normal
created: 2026-10-13
pr: 37
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

## Verification

Decided 2026-10-14: drop `format`. Branch `fix/alignment-over-pinata-cap`,
measured 2026-10-15.

- A unit test checks every SDK asset type with every field plus `_owner`
  against the cap: only `alignment` failed before (10); all 16 pass after.
  `variants` and `known_sites` are also at exactly 9.
- Real Pinata API: `main` refuses an `Alignment` upload with `_owner` at 10
  keys; on the branch a pinata-tier test uploads one with every field set,
  reads back exactly 9 keys, and deletes it.
- Unit tier 445, tasks tier 37 + 15 pass.

## Outcome

Shipped in PR #37 (merged 2026-10-15). `Alignment.format` is gone, so an
`Alignment` with every field set plus `_owner` is exactly 9 keyvalues and
uploads to Pinata. A unit test checks every SDK asset type at full width
against the cap.

Verified with that test (only `alignment` failed before, at 10; all 16 pass
after) and a pinata-tier test that uploads an `Alignment` with every field
set, reads back exactly 9 keys, and deletes it.

Left: `variants` and `known_sites` are also at exactly 9, so neither can gain
a declared field without losing one. Dropping `format` broke #31's new test on
`main` until #35.
