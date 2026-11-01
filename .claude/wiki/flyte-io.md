---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
  - src/stargazer/assets/asset.py
  - src/stargazer/utils/storage.py
---

# Flyte I/O

What crosses a task boundary by value and what by reference. Sources: [[flyte-sdk-examples#4. Type System]], [[flyte-sdk-examples#File Operations (Async)]], [[flyte-v2-docs#Task Programming]].

## By value

- **Primitives, collections, `Optional`, `Union`, enums, dataclasses and Pydantic models** are fully serialized, stored and deserialized between tasks.
- **A Pydantic model holding a `File` or `Dir`** needs `arbitrary_types_allowed`.
- **`max_inline_io_bytes`** caps a task's inline inputs and outputs, 100 MiB by default ([[flyte-task-environments]]).

## By reference

- **`flyte.io.File`**: `File.from_local(path)` uploads, `File.new_remote()` makes a file to stream into, `File.from_existing_remote(uri)` references one already stored. `open()` streams, `download()` fetches to a local path, `exists()` checks. Each has a `_sync` form for sync tasks.
- **`flyte.io.Dir`**: `Dir.from_local(path)`, then `walk()`, `list_files()` and `get_file(name)`.
- **`flyte.io.DataFrame`**: wraps a pandas, polars, pyarrow or dask frame; `from_df()` to make one, an `Annotated[..., "parquet"]` return type to fix the format, `open(pd.DataFrame).all()` to read it back. A task typed to take a pandas frame receives one converted. See [[flyte-v2-docs#DataFrames]].

## In Stargazer

- **An asset is a dataclass whose bytes travel as a `File`.** `Asset.path` is a `flyte.io.File` naming where the stored bytes live, so an asset's keyvalues pass by value and its file by reference. See [[provenance]] and `docs/architecture/types.md`.
- **`File.download()` can't read an `https://` path**, so gateway downloads use aiohttp directly. See [[storage#Tiers]].
