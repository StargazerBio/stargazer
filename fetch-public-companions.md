---
title: fetch() asks Pinata for companions on every call
status: doing
priority: normal
created: 2026-10-20
---

`Asset.fetch()` looks up the asset's companions with
`assemble(companion_of=<cid>)`. `StorageClient.query()` queries the user's
index and then, whenever `PINATA_JWT` is set, Pinata's API for every
combination of the filters, and merges the two, the user's row winning on a
shared CID (`src/stargazer/utils/storage.py`, `query`). On Union the key is
in every pod that fetches: `STARGAZER_SECRETS` is on `gatk_env`,
`scrna_env`, the per-notebook envs and the dashboard. So every `fetch()` on
the tenant makes a Pinata API call after the index query, whether or not
the asset is the user's own. Read from the code, not measured.

Pinata can't simply be skipped for private assets. CIDs are content
addresses, so a private copy of a public reference has the public one's CID
and picks up its public companions (`.fai`, `.dict`, bwa index), which helps
a user who hasn't built them.

**A possible bug, found in the same code.** The merge drops duplicates by
CID, not by filename. If the user's `ref.fa.bwt` and a public `ref.fa.bwt`
were built differently, both come back with different CIDs, and both are
written to the same directory (`_materialize` to `directory/name`), the
second overwriting the first. A tool could then read a bwa index mixed from
two builds. Inferred from the code, not reproduced. To reproduce, store a
companion locally whose filename matches a public companion of the same
parent with different bytes, and fetch the parent with a Pinata key set.

Two narrower rules, either of which also cuts the Pinata call in the common
case. Both change what users get, so it's a decision first:
- **Fill gaps only:** ask Pinata only when the user's index returns no
  companions.
- **One source per filename:** a public companion is dropped when the user
  has one with the same filename.

## Decision: fill gaps only

`fetch()` asks the public tier for an asset's companions only when the
user's own index holds none for its CID (`StorageClient.companions`).
`query()` keeps merging both tiers for every other `assemble()` caller.

- The common case, a user's own asset with its own companions, makes no
  Pinata call.
- A user's companions and public ones are never mixed, so a tool can't
  read an index from two builds.
- A private copy of a public reference with no companions of its own still
  gets the public `.fai`, `.dict` and aligner index.
- Accepted cost: a user with only some companions gets no public ones for
  the rest. The task that needs a missing one raises, naming it, per the
  rule that a task never makes up for a missing input.

## Repro (measured, unit test and script against `main`)

- Same filename only (user's `ref.fa.bwt`, a public `ref.fa.bwt` with
  other bytes): no overwrite. The user's bytes land, because `query()`
  lists the user's rows first and `_materialize` keeps an existing file.
  Pinata is still queried once.
- Partial overlap (user's `ref.fa.bwt`; public `ref.fa.bwt` and
  `ref.fa.sa`): the directory gets `my bwt` beside `public sa`, an index
  mixed from two builds. This is the bug that reproduced.

A related case this decision doesn't change is ticket
`stale-companion-cache`.
