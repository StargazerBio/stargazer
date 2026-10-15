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

- [x] Companions opt in with `_companion = True`, and `fetch()` asks only
  for those (55f43a2).
- [ ] One Pinata call per query, not one per combination of list values.
  The first piece passes `asset=[<6 companion keys>]`, and the public tier
  expands a list into one exact-match query per entry, so every `fetch()`
  went from 1 Pinata call to 6.
- [ ] `fetch()` asks only for the companion types that name this asset's
  type (a `<key>_cid` field), and skips the lookup when none do. Fetching
  reads, AnnData or a BQSR report then makes no round-trips at all.
- [ ] Undecided: skip Pinata for assets the user stored themselves, asking
  it only about assets that came from the public tier. Their companions are
  the user's own outputs, but a user's copy of a public file (same CID)
  would no longer pick up its public companions.
- [ ] Undecided: memoize companion lookups per process. Needs an upload of
  a companion to invalidate its parent's entry, since a local workflow runs
  every task in one process.

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
