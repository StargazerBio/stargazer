# Storage and Assets — Internals (agent reference)

The companion to the human-facing [configuration](../../../docs/architecture/configuration.md) and [types](../../../docs/architecture/types.md) docs. Per-function behavior (companion lookup order, Pinata caps and upload paths, `build_asset`, `specialize`) lives in the docstrings and comments of `utils/storage.py`, `utils/pinata.py` and `assets/`; this file holds what spans modules.

## Image builds

- Flyte fixes an image's registry when the image is *defined*, as `config.py` imports: from `FLYTE_IMAGE_REGISTRY` or `image.registry` in `./.flyte/config.yaml`, not from the config a later init reads. A registry in that file therefore leaks into any Union run from the same checkout.
- On an Apple-silicon devbox the cluster runs natively and `amd64` task pods run emulated. An arm64 node won't pull an image index with no arm64 entry, so devbox builds set `FLYTE_DOCKER_BUILD_EXTRA_ARGS=--provenance=false` to push a plain image.
- The package is in the task images, so a source change builds new ones. `.dockerignore` keeps docs, tests and local caches out of the build context so they don't.
- `image.builder` in the Flyte config is `local` (Docker daemon; pushes to `FLYTE_IMAGE_REGISTRY`) or `remote` (Union only).

## Provenance and extras

- `{asset_key}_cid` fields and `source_cid` record which input an output came from; only `companion_of` is followed by `fetch()`. Reads link their mate via `mate_cid`, which is neither.
- A task that builds a new asset from an input copies only the fields it sets; the input's extras don't pass to the output.
- `Notebook` is the one asset type no task produces: a workspace notebook becomes one when its owner publishes it from the dashboard.

## Ownership

`_owner` is stamped from `STARGAZER_OWNER` on every index row the storage client writes, and on public uploads by `PinataClient.upload()`. `PinataClient.update_metadata()` stamps nothing: its caller names the owner (the asset explorer's edit route uses the signed-in subject). `_owner` records who made a record and decides which public companions `fetch()` takes; it grants nothing, and on the public network anyone with the key can edit or delete any record.

## Tiers

- Nothing uses Pinata's private network. The asset explorer's Mine source is the user's index and store; its Public source calls the public network directly.
- `PinataClient.tus_create()` / `tus_patch()` exist so the dashboard's explorer can relay a browser's upload chunk by chunk.
- Gateway downloads use aiohttp directly: `flyte.io.File.download()` can't read an `https://` path.
