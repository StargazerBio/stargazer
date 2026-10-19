---
title: Publish an asset to the public tier
status: done
priority: normal
created: 2026-10-06
pr: 43
---

`publish(asset)` promotes a stored asset to Pinata's public network with its keyvalues and
`_owner`. The CID doesn't change. A follow-up from [plan 27](archive/27_asset_storage_index.md).

It's the step under every Publish button: on an asset (ticket
`assets-on-dashboard-home`) and on a notebook (ticket `public-notebooks`).
This ticket is the SDK half and an MCP tool; the buttons come with those
tickets.

## Design (2026-10-18)

- **`StorageClient.publish(cid)`** reads the user's index row, makes a local
  copy of the stored file (`download`), and uploads it to Pinata with the
  row's keyvalues (`PinataClient.upload`, which sends files over 100 MB in
  resumable chunks). `_owner` is restamped from `STARGAZER_OWNER`, as every
  upload is. Returns the public record.
- **The CID must come back the same.** Ours is computed to match Pinata's
  (`stargazer.utils.cid`), so a different CID is a bug: it raises, and the
  public copy is left for the caller to see.
- **The private row stays.** The asset is now in both tiers; `query` shows
  the user's row and drops the public duplicate by CID.
- **Refused before anything is sent:** no public tier (`PINATA_JWT` unset),
  a CID that isn't in the user's index, and keyvalues over Pinata's limits
  (nine keys, 250 characters each), which the client already checks.
- **One asset at a time.** Companions aren't published with it.
- **MCP:** `publish_file(cid)`.

## Pieces

- [x] Tests first, in `tests/utils/test_storage.py`, with a fake public tier
      that records what it's sent and assigns the CID the real one would:
  - a stored file published → the fake got its bytes and keyvalues,
    `_owner` included, and the record's CID is the stored CID
  - no public tier → refused; an unknown CID → refused; nothing sent
  - the public tier assigns a different CID → raises
- [x] `StorageClient.publish(cid)`.
- [x] MCP `publish_file(cid)` in `src/stargazer/server.py`, with a test
      beside the other tools'.
- [x] Pinata tier, against the real API: store a small random file, publish
      it, find it on the public network with the same CID and keyvalues,
      then delete it from Pinata.
- [x] Docs: `docs/architecture/configuration.md` (the public tier) and the
      MCP guide's tool list.

## Verified (2026-10-18)

Unit tier: 460 passed, the five new tests failing first. Pinata tier, real
API: a random file stored in a temp store and published came back on the
public network with the same CID and keyvalues, then was deleted from
Pinata. Branch `feat/publish-asset`, PR #43.

Found along the way: hosted notebook pods hold no Pinata key (measured
2026-10-17), so `publish` in a hosted notebook raises. It works in tasks, on
the dashboard and locally with a key. The Publish buttons will run on the
dashboard. Notebook pods get the key in ticket `notebook-pinata-key` (PR
#44, decided 2026-10-18); their terminals still scrub it.

## Outcome

Merged in #43 (2026-10-18). `StorageClient.publish(cid)` uploads one of the
user's stored files to Pinata's public network with its index row's
keyvalues, `_owner` restamped, and raises if Pinata's CID differs from
ours. The MCP server exposes it as `publish_file`. Verified with the unit
tier and against the real Pinata API (above).

Left: the Publish buttons on the dashboard (ticket `assets-on-dashboard-home`)
and publishing a notebook (ticket `public-notebooks`). Companions aren't
published with their asset.
