---
title: Asset.fetch() pulls every asset that records the CID
status: backlog
priority: high
created: 2026-10-09
---

`Asset.fetch()` pulls more than companions: any asset recording
`<key>_cid` comes along, so `Reference.fetch()` downloads every
`Alignment` made against it (`reference_cid`), and every task that
fetches the reference after alignment pays for them (measured against
an isolated store). Related to [cheaper-asset-fetch](cheaper-asset-fetch.md).

Found in the docs correctness sweep (2026-10-09, #18).
