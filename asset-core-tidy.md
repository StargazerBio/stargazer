---
title: asset-core-tidy
status: done
priority: normal
created: 2026-11-09
pr: 146
---

The asset base has three small pieces of accidental shape, found in a review of the core (2026-11-09). None changes what an asset is; each removes a second way of saying one thing.

1. **Two homes for the registry functions.** `specialize()` and `build_asset()` live in `assets/__init__.py`, but `Asset.fetch()` and `assemble()` in `assets/asset.py` need `specialize`, so they import it lazily from the package that imports them. The registry itself has two names, `Asset._registry` and `ASSET_REGISTRY`.
2. **Two dict shapes for one asset.** The index, the public tier and `specialize()` speak the record shape, `{cid, uri, name, keyvalues}`. `Asset.to_dict()` emits a different one, `{cid, path, name, keyvalues}`, and `from_dict()` reads it back. So over MCP, `query_files` returns `uri` and `upload_file` returns `path` for the same thing. `from_dict()` has no caller outside its tests.
3. **A stale version.** `stargazer.__version__` is the literal `"0.1.0"`; the package is versioned by calendar tag in `pyproject.toml`.

## Plan

On `refactor/asset-core-tidy`.

- [x] `assets/asset.py` holds the registry and both functions: a module-level `ASSET_REGISTRY: dict[str, type[Asset]] = {}` that `__init_subclass__` fills, then `specialize()` and `build_asset()` moved over unchanged. `Asset._registry` goes. `assets/__init__.py` re-exports the same names, so `from stargazer.assets import ASSET_REGISTRY, build_asset, specialize` still works (the infra dashboard and the assets tutorial import them from there). The lazy `from stargazer.assets import specialize` lines in `fetch()` and `assemble()` go; the lazy `stargazer.utils.storage` import stays, since storage imports `Asset`.
- [x] `Asset.to_dict()` returns the record shape: `{"cid", "uri", "name", "keyvalues"}`, `uri` being `self.path.path` or `None`. `from_dict()` is deleted: `specialize(asset.to_dict())` is the round trip. Tests in `tests/assets/test_asset.py`'s `TestDict` are rewritten for that: the shape, a typed asset, a bare one and an empty one each round-tripping through `specialize`.
- [x] `stargazer.__version__` is `importlib.metadata.version("stargazer-bio")`.
- [x] Docs: `docs/architecture/types.md` (the `to_dict()` / `from_dict()` line) and `docs/architecture/mcp-server.md` if it names the `path` key.

Assumptions made instead of asked: the MCP wire shape may change without a compatibility shim (project rule); `to_dict` keeps its name because `marshal_output` duck-types on it.

## Evidence (2026-11-09)

Typed by a cheap worker from the plan, diff read in full. `TestDict` failed first on `main`'s code (`KeyError: 'uri'`), then 182 passed across `tests/assets`, `tests/unit` and `tests/notebooks`. On an isolated store, MCP's `upload_file` and `query_files` return the same keys and equal `uri`s. `__version__` is `2026.10.30`. `docs/architecture/mcp-server.md` names no `path` key, so it's unchanged (all measured).

## Verification recipe

- `pixi run pytest tests/assets tests/unit` passes; the rewritten `TestDict` tests fail on `main` first (`KeyError: 'uri'`).
- `pixi run python -c "import stargazer; print(stargazer.__version__)"` prints `pyproject.toml`'s version.
- MCP surface: call `upload_file` then `query_files` on an isolated store and compare the two records' keys.

## Outcome

PR 146 merged 2026-11-10 with no review comments. Shipped: one record shape for an asset (`to_dict()` is the storage record `specialize()` reads) and the registry beside the class. Verified by the assets, unit and notebooks tests and the MCP surface on an isolated store (see Evidence). Nothing left.

Related: [[board]], [[lean-task-bodies]], [[task-environment-factory]].
