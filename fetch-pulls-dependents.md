---
title: Asset.fetch() pulls dependents and queries storage on every call
status: doing
priority: high
created: 2026-10-09
pr: 35
---

`Asset.fetch()` pulls more than companions: any asset recording
`<key>_cid` comes along, so `Reference.fetch()` downloads every
`Alignment` made against it (`reference_cid`), and every task that
fetches the reference after alignment pays for them (measured against
an isolated store).

It is also expensive to call. Even when the file is already in the cache,
`fetch()` looks up the asset's companions every time: one index query (an
HTTP call to the dashboard on Union) and, with `PINATA_JWT` set, Pinata API
calls (measured 2026-10-07). A task that fetches many assets pays that many
round-trips. Rolled in from `cheaper-asset-fetch` on 2026-10-15, because the
first fix made this worse (below).

Found in the docs correctness sweep (2026-10-09, #18).

## Plan

The first fix (55f43a2, rebased as fc2e220) told companions apart with a
`_companion` class flag, because `<parent>_cid` meant both "sits beside"
(`ReferenceIndex.reference_cid`) and "made from" (`Alignment.reference_cid`).
Decided 2026-10-15: the field name carries the meaning instead.

- [x] Companions opt in with `_companion = True`, and `fetch()` asks only
  for those (fc2e220).
- [ ] The six companion types link their parent with one shared field,
  `companion_of`, and the `_companion` flag goes. `fetch()` asks for
  `companion_of=<cid>`: one exact-match filter, so one index call and one
  Pinata call, as on `main`. The "made from" fields (`reference_cid`,
  `r1_cid`, `alignment_cid` on outputs, `variants_cid`, `source_cid`) keep
  their names and stay provenance only.
- [ ] Refuse a Pinata upload whose keys or values run past 250 characters
  before anything is sent, beside the 9-key check. Measured 2026-10-15 with
  probe uploads (all deleted): 250 accepted, 251 refused with `Metadata
  "keyvalues" keys and values must be less than 250 characters.` A cohort's
  `source_samples` list crosses it at about 20 sample IDs (arithmetic).

Not in this PR: making `fetch()` cheaper than `main`. Skipping Pinata for
assets the user stored (a user's copy of a public file would lose its public
companions) and memoizing lookups per process (an upload must invalidate)
were weighed and left out.

## Round-trips per fetch()

Fixtures seeded into an isolated store, Pinata replaced by a counting stub,
one `fetch()` of each type (2026-10-15):

| | `main` | branch at 55f43a2 |
|---|---|---|
| index queries | 1 | 1 |
| Pinata queries | 1 | 6 |

The same for reference, alignment, r1, variants and known_sites.

## Verification: companions only

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
