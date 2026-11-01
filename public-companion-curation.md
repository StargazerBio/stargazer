---
title: public-companion-curation
status: done
priority: normal
created: 2026-10-20
pr: 74
---

Any user can publish a public file with `companion_of` set to someone
else's public asset, and nothing decides which of those count. When
`fetch()` falls back to the public tier (the user has no companions of
their own, ticket [[fetch-public-companions]]), it takes every public record
whose `companion_of` is the asset's CID. A popular reference such as
GRCh38 will collect `.fai`, `.dict` and aligner indexes from many
publishers. The download grows with each one, and two publishers'
`ref.fa.bwt` built differently land in the same directory, where
`_materialize` keeps whichever came first. That's the mixed index from two
builds that ticket [[fetch-public-companions]] fixed for the user's own
files, back again inside the public tier. Inferred from the code, not
measured. Raised in the merge comment on PR #58.

Needs a curation rule before the code. Options to weigh:

- **One publisher per parent:** take the public companions from a single
  `_owner`, the one who published the parent or else a maintainer, so a
  set always comes from one build.
- **Curated set:** only records carrying a curation keyvalue that the
  maintainers set count as companions, and everyone else's are ignored by
  `fetch()`.
- **Gate at publish:** refuse a public companion whose parent isn't the
  publisher's own. The dashboard's public edits already check `_owner`.

Pinata caps new files at 9 keyvalues, so a new keyvalue on companions
needs counting against the assets that are already near the cap.

## Decided (2026-10-21, best assumption)

One publisher per parent: public companions count only when their `_owner`
also published the parent (`PinataClient.get` by CID); with no public parent,
none are taken. Gating at publish can't be enforced with a shared key, and a
curation keyvalue costs one of Pinata's 9 slots.

## Outcome

PR #74 merged (merge `719d7f1`) with only its first commit: public companions count only when their `_owner` matches the `_owner` of the parent's public record. Two later commits, made in its worktree minutes before the merge but never pushed, didn't ship, though the PR's description covers them: every public record needs an `_owner` (`PinataClient` refuses unowned writes, and reads skip unowned files), and `fetch()` also takes the caller's own public companions. They're ticket [[public-companion-owners]].

Verified on the merged commit with unit tests written first (fake public tier). Not driven live: the public tier holds no companions. No comments on the PR.
