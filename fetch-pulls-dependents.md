---
title: fetch-pulls-dependents
status: done
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
- [x] The six companion types link their parent with one shared field,
  `companion_of`, and the `_companion` flag goes. `fetch()` asks for
  `companion_of=<cid>`: one exact-match filter, so one index call and one
  Pinata call, as on `main`. The "made from" fields (`reference_cid`,
  `r1_cid`, `alignment_cid` on outputs, `variants_cid`, `source_cid`) keep
  their names and stay provenance only (988ff94).
- [x] Refuse a Pinata upload whose keys or values run past 250 characters
  before anything is sent, beside the 9-key check (2a7283f). Measured 2026-10-15 with
  probe uploads (all deleted): 250 accepted, 251 refused with `Metadata
  "keyvalues" keys and values must be less than 250 characters.` A cohort's
  `source_samples` list crosses it at about 20 sample IDs (arithmetic).
- [x] Drop `format="bam"` from `test_haplotype_caller.py` (5d633a5). #31
  added it and #37 removed `Alignment.format`; merged separately, they broke
  the tasks tier on `main` with a `TypeError`. Rolled in from
  `haplotype-caller-test-format` on 2026-10-15.

Not in this PR: making `fetch()` cheaper than `main`. Skipping Pinata for
assets the user stored (a user's copy of a public file would lose its public
companions) and memoizing lookups per process (an upload must invalidate)
were weighed and left out.

## Round-trips per fetch()

Fixtures seeded into an isolated store, Pinata replaced by a counting stub,
one `fetch()` of each type (2026-10-15):

| | `main` | branch at 55f43a2 | branch at 988ff94 |
|---|---|---|---|
| index queries | 1 | 1 | 1 |
| Pinata queries | 1 | 6 | 1 |

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

## Verification: companion_of and the length check

Measured 2026-10-15 on `fix/fetch-pulls-dependents`, rebased on `main` at
4c07685.

- Fixtures seeded into an isolated store, each input fetched into a fresh
  cache: the TP53 reference brings its 7 index and dictionary files and no
  BAMs; the duplicate-marked BAM brings only its `.bai`; each VCF its `.idx`.
  `main` still brings 5 BAMs with the reference, and the BQSR table and
  duplicate metrics with the marked BAM.
- New tests failed first for the expected reasons: no `companion_of` field,
  an untyped companion left behind, six public queries per fetch; for the
  length check, no raise, a request sent (401), and a 200 from the route.
  All pass after. Unit tier 454 passed.
- Tasks tier: scrna 16 passed; gatk and general 37 passed, 1 failed:
  `test_haplotype_caller` passes the removed `Alignment.format`, broken on
  `main` too. Fixed here (5d633a5); the test then passes in the gatk image.
- Devbox: `tests/devbox/test_germline.py` 2 passed (2m29s), every step in its
  own pod with the Pinata tier on. The dashboard's index holds the run's
  reference, aligner, alignment and variants indexes under `companion_of`;
  10 `variants_index` rows from earlier runs keep `variants_cid`.
- The Assets and Tasks tutorials export headless with exit 0 and render the
  new text.
- Dashboard graph: `relKeys()` and `relLabel()` run in node on sample
  metadata return `companion_of` as "companion of" and `reference_cid` as
  "reference". Not seen in a browser: the graph lists Pinata records, and
  the public network holds no companions.

## Outcome

Shipped in PR #35 (merged 2026-10-15). The six companion types link their
parent with one field, `companion_of`, and `fetch()` asks only for
`companion_of=<cid>`. A reference no longer brings the BAMs made against it,
and a fetch costs one index query and one Pinata query, as on `main` before.
The "made from" fields (`reference_cid`, `r1_cid`, `alignment_cid`,
`variants_cid`, `source_cid`) keep their names and are never followed. Pinata
uploads, signed upload URLs and metadata edits refuse a key or value over 250
characters before anything is sent, and the asset page's edit returns that as
a 400. The PR also dropped `test_haplotype_caller`'s removed `format`
argument.

Verified: unit tier 454; tasks tier 38 gatk and general, 16 scrna; devbox
germline 2 passed, with every index stored under `companion_of`; the Assets
and Tasks tutorials export with exit 0.

Left: companions stored before this change carry their old `<parent>_cid` key,
so `fetch()` leaves them behind until their indexing step runs again (10
`variants_index` rows on the devbox; the public network holds no companions).
The dashboard graph's "companion of" edge was checked in node, not seen in a
browser. Making `fetch()` cheaper than `main` was weighed and left out.

Related: [[fetch-public-companions]], [[stale-companion-cache]].
