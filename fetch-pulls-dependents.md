---
title: Asset.fetch() pulls every asset that records the CID
status: review
priority: high
created: 2026-10-09
pr: 35
---

`Asset.fetch()` pulls more than companions: any asset recording
`<key>_cid` comes along, so `Reference.fetch()` downloads every
`Alignment` made against it (`reference_cid`), and every task that
fetches the reference after alignment pays for them (measured against
an isolated store). Related to [cheaper-asset-fetch](cheaper-asset-fetch.md).

Found in the docs correctness sweep (2026-10-09, #18).

## Verification

Branch `fix/fetch-pulls-dependents`, measured 2026-10-14. Companions opt in
with `_companion = True` (the six index and dictionary types), and `fetch()`
asks only for those.

- With the test fixtures seeded into an isolated store, `fetch()` on the
  TP53 reference brought its 7 index and dictionary files plus 5 BAMs on
  `main`, and only the 7 on the branch. The duplicate-marked BAM brought its
  `.bai`, the BQSR table and the duplicate metrics on `main`; only the
  `.bai` on the branch.
- New unit test fails before and passes after; unit tier 430, tasks tier
  37 + 15 pass; the Assets and Tasks tutorials export with exit 0.
- AnnData was never affected: its outputs record `source_cid`, not
  `anndata_cid`.
