---
sources:
  - docs/architecture/types.md
  - src/stargazer/assets/asset.py
  - src/stargazer/assets/notebook.py
---

# Provenance

How an asset records where it came from, beneath `docs/architecture/types.md`.

- **Two kinds of derivation field.** `{asset_key}_cid` fields and `source_cid` record which input an output came from. Only `companion_of` is followed by `fetch()`. Reads link their mate through `mate_cid`, which is neither.
- **Extras don't pass through a task.** A task that builds a new asset from an input copies only the fields it sets; the input's extras don't pass to the output.
- **`Notebook` is the one asset type no task produces.** A workspace notebook becomes one when its owner publishes it from the dashboard. See [[notebooks]].

## Related

- [[storage]]: `_owner`, which decides which public companions `fetch()` takes
