---
title: Curate which public companions a popular asset gets
status: backlog
priority: normal
created: 2026-10-20
---

Any user can publish a public file with `companion_of` set to someone
else's public asset, and nothing decides which of those count. When
`fetch()` falls back to the public tier (the user has no companions of
their own, ticket `fetch-public-companions`), it takes every public record
whose `companion_of` is the asset's CID. A popular reference such as
GRCh38 will collect `.fai`, `.dict` and aligner indexes from many
publishers. The download grows with each one, and two publishers'
`ref.fa.bwt` built differently land in the same directory, where
`_materialize` keeps whichever came first. That's the mixed index from two
builds that ticket `fetch-public-companions` fixed for the user's own
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
