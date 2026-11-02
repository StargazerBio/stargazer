---
title: storage-consolidation
status: done
priority: normal
created: 2026-03-11
---

# Storage Consolidation

Merge `storage.py` into `local_storage.py` and consolidate config.

## Current State

```
src/stargazer/
├── config.py                  # Task environments (gatk_env) + logger
└── utils/
    ├── config.py              # Env var settings (PINATA_JWT, STARGAZER_LOCAL, etc.)
    ├── storage.py             # StorageClient protocol + get_client() + default_client
    ├── local_storage.py       # LocalStorageClient (the only StorageClient impl)
    └── pinata.py              # PinataClient (remote transport, not a StorageClient)
```

**Problem:** `storage.py` is a 30-line file with a protocol that has exactly one implementation, a trivial factory, and a module-level singleton. It exists purely as indirection.

## Plan

### 1. Rename `stargazer/config.py` → `stargazer/task_config.py`

It only contains `gatk_env` and `logger` — task infrastructure, not app config. The name `config.py` at the package root suggests it's the main config, which is confusing now that `utils/config.py` holds the actual env var settings.

- Rename file
- Update all imports (`from stargazer.config import` → `from stargazer.task_config import`)
- ~15 files in `tasks/` and `workflows/` to update (mechanical find-replace)

### 2. Move `utils/config.py` → `stargazer/config.py`

Now that the package-root `config.py` is freed up, the env var config belongs there. It's not a utility — it's project-level configuration that everything depends on.

- Move file
- Update imports in `utils/storage.py`, `utils/local_storage.py`, `utils/pinata.py`, `server.py`

### 3. Merge `storage.py` into `local_storage.py`

Move `StorageClient` protocol, `get_client()`, and `default_client` into `local_storage.py`.

- Move protocol, factory, and singleton into `local_storage.py`
- Replace `storage.py` with re-exports for backwards compat:
  ```python
  from stargazer.utils.local_storage import StorageClient, get_client, default_client
  ```
- Update `utils/__init__.py` and `stargazer/__init__.py` to import from `local_storage`
- Update spec references in docstrings

### 4. Evaluate dropping `StorageClient` protocol

`StorageClient` is only implemented by `LocalStorageClient`. The protocol adds indirection without polymorphism. Consider replacing protocol type hints with `LocalStorageClient` directly.

**Hold on this** — the protocol is useful if we ever want to mock storage in tests without subclassing. Skip unless it causes friction.

## Target State

```
src/stargazer/
├── config.py                  # Env var settings (moved from utils/config.py)
├── task_config.py             # Task environments (gatk_env) + logger
└── utils/
    ├── storage.py             # Re-export shim (StorageClient, get_client, default_client)
    ├── local_storage.py       # LocalStorageClient + StorageClient protocol + get_client()
    └── pinata.py              # PinataClient (remote transport)
```

## Order of Operations

1. Rename `config.py` → `task_config.py` + update imports → run tests
2. Move `utils/config.py` → `config.py` + update imports → run tests
3. Merge `storage.py` → `local_storage.py` + leave re-export shim → run tests
4. `ruff --fix` after each step

## Outcome

Implemented 2026-03-11 (`b57c8b5`, then `f7ca72f` and `75b0c57`): the env var config consolidated into project config, and the mode variable from [[stargazer-mode-config]] removed. [[asset-storage-index]] later rebuilt the storage modules.
