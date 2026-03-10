# Modes

Stargazer uses a single configuration surface to control both storage backend and execution context. One env var (`STARGAZER_MODE`) determines the mode; credential availability refines storage selection within that mode.

## Mode Summary

| Mode | Storage | Execution | Env Requirements |
|------|---------|-----------|------------------|
| **Local** | Filesystem (`LocalStorageClient`) | Flyte local | None |
| **Local + Pinata** | IPFS via Pinata (`PinataClient`) | Flyte local | `PINATA_JWT` |
| **Cloud** | IPFS via Pinata (`PinataClient`) | Flyte remote (Union) | `PINATA_JWT`, Union config |

### Local Mode

The default. Files are stored on the local filesystem under `STARGAZER_LOCAL` (defaults to `~/.stargazer/local`). Metadata is indexed in a TinyDB database. No credentials required.

When `PINATA_JWT` is present, local mode automatically upgrades storage to Pinata. Execution remains local — only the storage backend changes.

### Cloud Mode

`STARGAZER_MODE=cloud` implies remote execution on Union and Pinata storage. Tasks are submitted to Union's Flyte cluster.

## Configuration

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `STARGAZER_MODE` | `local` or `cloud` | `local` | No |
| `PINATA_JWT` | Pinata API authentication | — | Only for Pinata storage or cloud mode |
| `PINATA_GATEWAY` | IPFS gateway URL | `gateway.pinata.cloud` | Only when using Pinata |
| `STARGAZER_LOCAL` | Local storage directory | `~/.stargazer/local` | No |

## Resolution Logic

1. Read `STARGAZER_MODE` from environment (default: `local`)
2. If `cloud`: return `PinataClient` (require `PINATA_JWT`)
3. If `local` and `PINATA_JWT` is set: return `PinataClient`
4. If `local` and no `PINATA_JWT`: return `LocalStorageClient`

This logic lives in `get_client()` in `storage.py`. Consumers never inspect the mode directly — they call `StorageClient` methods and the correct backend handles it.

## Storage Client Protocol

All backends implement:

```
StorageClient
├── upload_file(path, keyvalues, public) → IpFile
├── download_file(ipfile, dest) → IpFile
├── query_files(keyvalues, public) → list[IpFile]
└── delete_file(ipfile) → None
```

The `public` parameter is per-call, not global. Private is the default.

## Testing

Tests run in local mode with no `PINATA_JWT`. The test harness sets `STARGAZER_MODE=local`, points `LocalStorageClient` at a temporary directory, and never mutates client internals. Tests that need Pinata behavior mock the API or skip.
