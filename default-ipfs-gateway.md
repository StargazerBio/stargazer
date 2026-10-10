---
title: The default IPFS gateway no longer serves files
status: backlog
priority: high
created: 2026-10-09
---

The default `PINATA_GATEWAY`, `https://dweb.link`, no longer serves
files: every request answers 429 "This IPFS gateway is switching to a
service worker gateway only" (`sunset: 21 Sep 2026`), so
`fetch_resource_bundle` and any public download fail on a default
config, and with them the README quickstart. `gateway.pinata.cloud`
answered a full download with a Cloudflare challenge (429) and
`w3s.link` with 429 (all measured 2026-10-09). The account's dedicated
gateway (`<name>.mypinata.cloud`) served the demo files during plan 27,
but anonymous downloads through it spend account bandwidth. Picking the
default is a decision, not a one-line fix.

Found in the docs correctness sweep (2026-10-09, #18).
