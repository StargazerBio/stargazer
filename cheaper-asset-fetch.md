---
title: Make Asset.fetch() cheaper
status: next
priority: high
created: 2026-10-08
---

Even when the file is already in the cache, `fetch()` looks up the asset's companions every time: one index
query (an HTTP call to the dashboard on Union) and, with `PINATA_JWT` set,
one Pinata API call (measured 2026-10-07). A task that fetches many assets
pays that many round-trips. Options: memoize companion lookups per
process, or ask Pinata only about assets that came from the public tier.
