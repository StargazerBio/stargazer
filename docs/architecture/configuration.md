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
| `PINATA_GATEWAY` | Public IPFS gateway URL | `https://dweb.link` | No (set to empty string to disable) |
| `PINATA_VISIBILITY` | `public` or `private` | `private` | No |

## Resolution Logic

1. If `PINATA_JWT` is set: attach `PinataClient` remote
2. If no JWT: no remote (public gateway still available for downloads)

Always returns `LocalStorageClient`. The remote is optional.

## Download Flow

```mermaid
flowchart TD
    Start([Download requested]) --> A{path exists?}
    A -->|Yes| Done([Return])
    A -->|No| B{CID in local cache?}
    B -->|Yes| Done
    B -->|No| C{local_ CID?}
    C -->|Yes| D("Look up TinyDB") --> Done
    C -->|No| E{Remote + private\nvisibility?}
    E -->|Yes| F("Signed URL download → cache") --> Done
    E -->|No| G("Public IPFS gateway → fetch + cache") --> Done
```

## Storage Client Protocol

All storage operations go through `LocalStorageClient`:

```mermaid
flowchart LR
    C[("LocalStorageClient")]

    C --> U("upload(component)\nremote or local — never both")
    C --> D("download(component)\nbool — cache → remote (private) → public gateway")
    C --> Q("query(keyvalues)\nremote or local TinyDB")
    C --> X("delete(component)\nremote or local")
```

The two modes are explicit and separate:

- **JWT set (remote mode):** Pinata owns metadata and bytes. TinyDB is not involved. Upload, query, and delete go to Pinata. Downloads fetch bytes by CID via signed URL or public gateway, cached locally as bytes only.
- **No JWT (local mode):** TinyDB owns metadata. Local filesystem stores bytes. Downloads check TinyDB, then fall back to the public IPFS gateway for cache misses on bytes.

## Resource Bundles

Bundles are curated sets of files (reference genomes, demo datasets) defined as YAML manifests in `src/stargazer/bundles/`. Each manifest lists CIDs and their keyvalues, with a `bundle` keyvalue on each file for queryability.

### Hydration Flow

`fetch_resource_bundle(bundle_name)` downloads files by CID:

```mermaid
flowchart TD
    Start([fetch_resource_bundle]) --> A("Load YAML manifest by name")
    A --> B{JWT set?}
    B -->|Yes| C("Files already registered in Pinata\nDownload bytes by CID\nNo TinyDB writes")
    B -->|No| D("Seed TinyDB with manifest keyvalues\nDownload bytes from public IPFS gateway")
    C --> Done([Assets queryable via assemble])
    D --> Done
```

### Bundle Format

```yaml
name: scrna_demo
description: Sample scRNA-seq mouse brain data for demo workflows
files:
  - cid: QmABC...
    keyvalues:
      asset: anndata
      bundle: scrna_demo
      sample_id: s1d1
      stage: raw
      organism: mouse
```

After hydration, bundled assets are queryable via `assemble()` and `query_files` like any other asset.

