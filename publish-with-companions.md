---
title: publish-with-companions
status: backlog
priority: normal
created: 2026-11-01
---

Publishing an asset should publish its companions with it, so a reference
goes public as the set of files tools need: the FASTA, its `.fai`, `.dict`
and aligner index. Today `StorageClient.publish(cid)` (and MCP
`publish_file`) puts one file on the public tier, and its companions stay
private (ticket [[publish-asset]]: "Companions aren't published with it").
A user who publishes a reference and forgets the indices hands everyone
the FASTA alone, and every downstream `fetch()` gets no public companions
to fill in with.

This is the gap between what the docs want to say about the asset graph
and what's true: work done once (indexing a reference) reaching everyone
who fetches that reference. Opened from the docs revision that introduces
the asset graph and "collaboration without coordination".

## Shape

- `publish(cid)` also publishes the user's own companions of `cid`
  (`index.query({"companion_of": cid})`, newest per name, the same rows
  `companions()` takes first), each with its own keyvalues and `_owner`
  restamped. `fetch()` already takes public companions only from the
  parent's publisher (ticket [[public-companion-curation]]), and the same
  caller publishes both, so they count.
- Check every companion against Pinata's limits (9 keyvalues, 250
  characters) before sending anything, so a set doesn't go half public.
- A companion that's already public with the same CID is skipped.
- Return the parent's record and the companions'. The MCP tool reports
  what went public.

## Open questions

- Opt out (`companions=False`) or always? Start with always; an asset's
  companions are what make it usable.
- A companion of a companion (none exist today): ignore until one does.

## Pieces

- [ ] Unit tests in `tests/utils/test_storage.py` against the fake public
      tier: a parent with two companions publishes three records, same
      CIDs; a companion over the keyvalue limit refuses the whole set with
      nothing sent; an already-public companion isn't sent again.
- [ ] `StorageClient.publish` and MCP `publish_file`.
- [ ] Pinata tier: publish a small parent and companion, `fetch()` the
      parent from an isolated store with no companions of its own and see
      the public companion land beside it, then delete both from Pinata.
- [ ] Docs: the public tier in `docs/architecture/configuration.md`.
