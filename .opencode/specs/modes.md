# Modes Specification

## Design Goals

Stargazer uses a single configuration surface to control both storage backend and execution context. One env var (`STARGAZER_MODE`) determines the mode; credential availability refines storage selection within that mode. This eliminates invalid configuration combinations by construction and makes the system's behavior predictable from a glance at the environment.

## Modes

There are three distinct operational modes:

| Mode | Storage | Execution | Env Requirements |
|------|---------|-----------|------------------|
| **Local** | Filesystem (`LocalStorageClient`) | Flyte local | None |
| **Local + Pinata** | IPFS via Pinata (`PinataClient`) | Flyte local | `PINATA_JWT` |
| **Cloud** | IPFS via Pinata (`PinataClient`) | Flyte remote (Union) | `PINATA_JWT`, Union config |

All remote storage goes through Pinata. There is no separate cloud-hosted storage backend.

### Local Mode

The default. Files are stored on the local filesystem under `STARGAZER_LOCAL` (defaults to `~/.stargazer/local`). Metadata is indexed in a TinyDB database (`stargazer_local.json`). No credentials required.

When `PINATA_JWT` is present, local mode automatically upgrades storage to Pinata. Execution remains local — only the storage backend changes. This upgrade is silent and requires no additional configuration.

### Cloud Mode

`STARGAZER_MODE=cloud` implies remote execution on Union and Pinata storage. `PINATA_JWT` is required. Tasks are submitted to Union's Flyte cluster rather than running locally.

## Configuration

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `STARGAZER_MODE` | `local` or `cloud` | `local` | No |
| `PINATA_JWT` | Pinata API authentication | — | Only for Pinata storage or cloud mode |
| `PINATA_GATEWAY` | IPFS gateway URL | `gateway.pinata.cloud` | Only when using Pinata |
| `STARGAZER_LOCAL` | Local storage directory | `~/.stargazer/local` | No |

No other env vars control mode or storage selection.

## Mode Resolution

Mode resolution follows a strict precedence:

1. Read `STARGAZER_MODE` from environment (default: `local`)
2. If `cloud`: return `PinataClient` (require `PINATA_JWT`)
3. If `local` and `PINATA_JWT` is set: return `PinataClient`
4. If `local` and no `PINATA_JWT`: return `LocalStorageClient`

This logic lives in `get_client()` in `storage.py`. The resolved client is the single storage interface for the entire application. Consumers never inspect the mode directly — they call `StorageClient` methods and the correct backend handles it.

## Storage Client Protocol

All storage backends implement the same protocol:

```
StorageClient
├── upload_file(path, keyvalues, public) → IpFile
├── download_file(ipfile, dest) → IpFile
├── query_files(keyvalues, public) → list[IpFile]
└── delete_file(ipfile) → None
```

The `public` parameter is per-call, not a global setting. Private is the default.

## Testing Implications

Tests run in local mode with no `PINATA_JWT`. The test harness:

1. Sets `STARGAZER_MODE=local` and removes `PINATA_JWT` from the environment
2. Points `LocalStorageClient` at a temporary directory for isolation
3. Never mutates client internals — mode is controlled entirely through environment variables

Tests that need Pinata behavior mock the Pinata API or skip if no JWT is available.
