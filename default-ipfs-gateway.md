---
title: The default IPFS gateway no longer serves files
status: done
priority: high
created: 2026-10-09
pr: 36
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

## Verification

Decided 2026-10-14: default to the account's dedicated gateway
(`https://maroon-written-fowl-769.mypinata.cloud`), for every download,
anonymous asset-page ones included. Branch `fix/default-ipfs-gateway`.

- Gateways re-measured 2026-10-15: `dweb.link` and `w3s.link` 429, `ipfs.io`
  and `cloudflare-ipfs.com` don't connect, `4everland.io` 504,
  `trustless-gateway.link` 521, `gateway.pinata.cloud` 200 this time. The
  dedicated gateway served the 562 KB demo file anonymously in 1.8 s.
- Default config (`PINATA_GATEWAY` unset), `fetch_bundle("variant_calling_demo")`:
  429 from `dweb.link` on `main`; all three files on the branch.
- Not done: the README quickstart's `stargazer-chat` image is pushed by
  hand and keeps the old default until it's rebuilt.

## Outcome

Shipped in PR #36 (merged 2026-10-15). `PINATA_GATEWAY` defaults to the
account's dedicated gateway, `https://maroon-written-fowl-769.mypinata.cloud`,
for every download, anonymous ones included.

Verified: on a default config, `fetch_bundle("variant_calling_demo")` fetched
all three files (429 from `dweb.link` on `main`); the dedicated gateway served
the demo file anonymously in 1.8 s.

Left: anonymous downloads now spend the account's gateway bandwidth. The
README quickstart's `stargazer-chat` image keeps the old default until it's
rebuilt: ticket `rebuild-chat-image`.
