---
title: bit-for-bit-snapshots
status: done
priority: low
created: 2026-06-10
---

Snapshots currently freeze the notebook *source* only; add image-digest pinning and a CID input/output manifest so a snapshot re-run is bit-for-bit. (Was a Deferred note in `docs/architecture/app.md`.)

## Outcome

Superseded (2026-10-18). Snapshots were removed in #41 (ticket
`save-whole-workspace`). A notebook is either a file in a workspace or, once
published, an asset (ticket `public-notebooks`), so reproducing a published
notebook's run is that ticket's question now.
