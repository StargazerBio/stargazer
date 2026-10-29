---
title: stale-companion-cache
status: maybe
priority: low
created: 2026-10-20
---

`fetch()` links companions into the parent's cache directory,
`<STARGAZER_LOCAL>/<parent cid>/<companion name>`, and `_materialize` keeps
a file already there. That directory is named by the parent's CID, not the
companion's, so the rule that a cached file never changes doesn't hold for
it. When a persistent cache already holds a public companion from an
earlier fetch (the user had none then), and the user later stores their
own with the same filename, the next fetch keeps the public file and the
user's is never linked in.

Measured with a script against an isolated store and a fake public tier,
on `main` and on `fix/fetch-public-companions` alike: fetch 1 lands
`public bwt`; after the user stores `my bwt`, fetch 2 still shows
`public bwt`.

Who it reaches: a local cache (`~/.stargazer/local`) and any long-lived
pod that fetches the same parent twice. A Union task pod starts with an
empty cache, so a task run there isn't affected (inferred, not measured).
A tool that builds deterministically writes the same bytes either way, so
it matters only when the two builds differ.

One way: when linking a companion, replace a file at the target that isn't
the same file as the companion's own cache copy (`os.path.samefile`).
