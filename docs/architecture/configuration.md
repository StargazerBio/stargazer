# Configuration

Stargazer uses `LocalStorageClient` as the single storage client. It always handles caching and local metadata. When `PINATA_JWT` is available, a `PinataClient` remote is attached for authenticated operations. Public IPFS gateway access is always available — downloading a public CID works out of the box with no configuration, the same way `docker run ubuntu` pulls from Docker Hub by default.

## Summary

| Setup | Download | Upload / Query / Delete | Env Requirements |
|-------|----------|------------------------|------------------|
| **Default** | Cache + public IPFS gateway | Local only (TinyDB) | None |
| **JWT + public** | Cache + public IPFS gateway | Pinata API (public network) | `PINATA_JWT`, `PINATA_VISIBILITY=public` |
| **JWT + private** | Cache + signed URLs | Pinata API (private network) | `PINATA_JWT` |

### Default (no JWT)

Files are stored on the local filesystem under `STARGAZER_LOCAL` (defaults to `~/.stargazer/local`). Metadata is indexed in a TinyDB database.

Downloads check the local cache first. On a cache miss, the public IPFS gateway is used to fetch the file — no credentials needed for public CIDs.

### With JWT

When `PINATA_JWT` is present, a `PinataClient` remote is attached. This enables upload, query, and delete via the Pinata API. `PINATA_VISIBILITY` controls whether files are uploaded to the public or private network:

- **private** (default): uploads as private, downloads use signed URLs, queries hit `/files/private`
- **public**: uploads as public, downloads use the public IPFS gateway, queries hit `/files/public`

> **Warning — ephemeral compute:** Without `PINATA_JWT`, uploads and metadata are stored only on the local filesystem. In ephemeral compute environments (e.g. Union/Flyte pods, CI runners, serverless functions), local storage is lost when the container exits. Set `PINATA_JWT` to persist outputs beyond the lifetime of the compute instance.

## Environment Variables

All env vars are centralized in `utils/config.py`. If set (even to empty string), the value is used exactly. If unset, the default applies.

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `STARGAZER_LOCAL` | Local storage directory | `~/.stargazer/local` | No |
| `PINATA_JWT` | Pinata API authentication | None (unset) | Only for authenticated operations |
| `PINATA_GATEWAY` | Public IPFS gateway URL | `https://gateway.pinata.cloud` | No (set to empty string to disable) |
| `PINATA_VISIBILITY` | `public` or `private` | `private` | No |

## Resolution Logic

1. If `PINATA_JWT` is set: attach `PinataClient` remote
2. If no JWT: no remote (public gateway still available for downloads)

Always returns `LocalStorageClient`. The remote is optional.

## Download Flow

```
1. component.path exists?           → return
2. CID in local cache?              → return
3. local_ CID?                      → look up TinyDB → return
4. Remote + private visibility?     → signed URL download → cache → return
5. Public IPFS gateway              → fetch → cache → return
```

## Storage Client Protocol

All storage operations go through `LocalStorageClient`:

```
StorageClient
├── upload(component)       → remote or local
├── download(component)     → cache → remote (private) → public gateway
├── query(keyvalues)        → remote or local TinyDB
└── delete(component)       → remote or local
```

## Testing

Tests run with no `PINATA_JWT`. The test harness points `LocalStorageClient` at a temporary directory and never mutates client internals. Tests that need Pinata behavior mock the API or skip.
