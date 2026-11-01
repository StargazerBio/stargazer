---
sources:
  - docs/architecture/configuration.md
  - docs/architecture/types.md
  - src/stargazer/utils/storage.py
  - src/stargazer/utils/pinata.py
---

# Storage

What spans the storage modules, beneath `docs/architecture/configuration.md` and `docs/architecture/types.md`. Per-function behavior (companion lookup order, Pinata caps and upload paths, `build_asset`, `specialize`) lives in the docstrings and comments of `utils/storage.py`, `utils/pinata.py` and `assets/`.

## Ownership

- **`_owner` is stamped from `STARGAZER_OWNER`** on every index row the storage client writes, and on public uploads by `PinataClient.upload()`.
- **`PinataClient.update_metadata()` stamps nothing.** Its caller names the owner: the asset explorer's edit route uses the signed-in subject.
- **`_owner` records, it doesn't authorize.** It records who made a record and decides which public companions `fetch()` takes (see [[provenance]]). It grants nothing: on the public network anyone with the key can edit or delete any record.

## Tiers

- **Nothing uses Pinata's private network.** The asset explorer's Mine source is the user's index and store; its Public source calls the public network directly.
- **`PinataClient.tus_create()` and `tus_patch()`** exist so the dashboard's explorer can relay a browser's upload chunk by chunk.
- **Gateway downloads use aiohttp directly**, because `flyte.io.File.download()` can't read an `https://` path. See [[flyte-io]].

## Related

- [[provenance]]: the fields that tie an asset to its inputs
- [[runtime]]: a notebook pod hydrates and saves its workspace through the store
