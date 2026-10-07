# 27 — Asset Storage on the Object Store, Indexed per User

Move asset bytes off Pinata and into object storage, and move the metadata
index into a SQLite database. On Union, each user's dashboard owns that
database: tasks and notebook pods upload files straight to the bucket and send
the dashboard one small row per asset. On a laptop the same database is a
local file, so local mode and the hosted deploy share one code path.
`assemble()` becomes a real query.

**Why.** Pinata does three jobs today: it stores the bytes, holds the keyvalue
index, and publishes public data. That makes it hard to move off. On Union it
means every intermediate BAM and h5ad leaves us-west-2 and comes back, under a
10 GiB per-file cap that a WGS BAM exceeds. The local fallback (TinyDB plus the
filesystem) is a second, separate mode, and it doesn't survive an ephemeral
pod. Union Artifacts would give a hosted index, but the open-source backend has
no artifact service. Splitting the three jobs lets each go to the right place:
bytes to whatever object store `flyte.storage` reaches, the index to SQLite we
own, and IPFS kept for publishing.

Isolation and security are out of scope: assumed solvable, and tracked on the
ROADMAP (**Per-user storage isolation**, **Org-wide platform key in every
pod**).

## What changes

| | Today | After |
|---|---|---|
| Where task outputs go | Pinata, or local disk without a JWT | The object store: `file://` on a laptop, the tenant bucket on Union |
| How `assemble()` finds them | Pinata's keyvalue filter, or a TinyDB scan | A SQL query against the user's index |
| Asset identity | IPFS CID from Pinata, or `local_<md5>` | IPFS CID computed locally, everywhere |
| An asset's file handle | `path: Path` | `file: flyte.io.File` |
| The dashboard's view of your assets | Pinata listing (off on Union) | Its own database |
| Publishing to IPFS | Implicit in every upload | An explicit step (follow-up) |

The SDK surface (`assemble`, `Asset.fetch`, `Asset.update`) keeps its shape.

## Verified (2026-10-06)

Measured while designing this plan unless marked otherwise.

- **Pinata's CIDs can be computed locally, offline.** About 60 lines of
  standard-library Python (UnixFS, CIDv1, raw leaves, 256 KiB chunks, balanced
  layout, 174 links per node, sha2-256) reproduced the manifest CID of all four
  bundle files tried: `GRCh38_TP53.fa` (one block, `bafkrei…`), both
  `NA12829_TP53_R*.fq.gz` (three chunks), and `s1d1.h5ad` (116 MB, a two-level
  tree). Files over about 7.4 GiB need a third tree level; that case is
  untested (Q13).
- **The artifact service is Union-only.** `flyte.remote.Artifact.list_names()`
  answers on the tenant and returns `ConnectError Not Found` on the devbox's
  open-source backend.
- **A dataclass holding a `flyte.io.File` round-trips through Flyte's type
  engine** (flyte 2.10.7) with the file's path and hash intact.
- **`File.from_local(path, remote_destination=…, hash_method=…)`** writes to a
  path we choose, and a string `hash_method` becomes the file's cache key.
  `File.from_existing_remote(uri, file_cache_key=…)` rebuilds a handle without
  downloading. *(SDK source.)*
- **The storage seam is narrow.** Tasks, workflows and notebooks touch storage
  only through `Asset.fetch()`, `Asset.update()`, `assemble()` and
  `default_client.local_dir` (23 call sites, all `local_dir`, used as scratch
  space). No task calls Pinata directly.
- **The dashboard runs at most one replica**: `replicas=(0, 1)`, scale-down
  after an hour idle (`app/admin_app.py`). One replica means one SQLite writer.
- **App disk doesn't persist.** Union's auto-scaling docs: "stateful apps
  require external state stores; local disk/memory are not preserved during
  scale-down". `Resources(disk=)` is ephemeral storage, and apps take no
  volumes.
- **Apps have an internal address.** `env.endpoint` and
  `AppEndpoint(public=False)` resolve through `INTERNAL_APP_ENDPOINT_PATTERN`
  when the pod has it set, and fall back to the public URL otherwise *(SDK
  source)*. Union's serving-graph example calls one `requires_auth=True` app
  from another over that address with no auth headers *(docs; not tested)*.
- **Bearer tokens pass the app gate** *(measured in an earlier session)*, so a
  laptop can call the dashboard's public URL with the CLI's token.
- **A laptop can't reach the tenant bucket directly.** A read-only listing fell
  back to the EC2 metadata endpoint and failed: there are no AWS credentials
  locally.

## Settled design decisions

Recorded so they aren't relitigated mid-build.

- **Bytes and index are separate.** Bytes live in the object store, the index
  in SQLite, and local disk is a read-through cache for bytes.
- **Identity is the IPFS CID, computed locally** with Pinata's parameters. The
  `cid` field keeps its name and means what it says: a published file's CID
  equals its working identity, and bundle CIDs match locally computed ones.
- **Blobs are content-addressed**: `<STORE_ROOT>/blobs/<cid>`. An upload whose
  blob already exists skips the transfer.
- **`Asset.path: Path` becomes `Asset.file: flyte.io.File`.** `update()`
  computes the CID, uploads with
  `File.from_local(path, remote_destination=…/blobs/<cid>, hash_method=cid)` so
  Flyte's cache key is the CID, then writes the index row. A row rebuilds the
  handle with `File.from_existing_remote(uri, file_cache_key=cid)`.
- **Local cache layout**: `<STARGAZER_LOCAL>/<cid>/<name>`, so a downloaded
  file keeps its real filename (GATK refuses inputs without it).
- **Every indexed asset's bytes are in the store.** Importing a bundle fetches
  it from the IPFS gateway once, checks its CID locally, and puts it in the
  store. IPFS is a source for imports and a destination for publishing, never a
  location a row points at.
- **The index is one SQLite table**, filtered with `json_extract`:

  ```sql
  CREATE TABLE assets (
    cid        TEXT PRIMARY KEY,
    uri        TEXT NOT NULL,   -- where the bytes live (file://…, s3://…)
    name       TEXT NOT NULL,   -- original filename
    keyvalues  TEXT NOT NULL,   -- JSON object
    created_at TEXT NOT NULL
  );
  ```

  Semantics match `query()` today: exact match, with every filter key ANDed. A
  list value matches any of its entries, in one query rather than a cartesian
  product of queries. The companion lookup (`<asset_key>_cid = X`) is an
  ordinary query.
- **One writer, first come first served.** The process that owns the file
  holds one write connection behind an `asyncio.Lock`, so requests wait their
  turn in arrival order. WAL mode lets reads run alongside writes without the
  lock. `update_metadata` reads, merges and writes under the lock, so
  concurrent merges can't drop each other's keys.
- **A write returns only after it commits**, so a downstream task always finds
  its upstream task's rows.
- **Upserts are keyed on the CID and idempotent**, so clients retry freely
  (with backoff on connection errors and 5xx).
- **On Union, each user's dashboard owns their index** and serves it over a
  small HTTP API: upsert, query, merge, delete. Files never pass through it.
- **One setting picks the index backend.** `STARGAZER_INDEX_URL=sqlite:///…`
  opens the file directly (laptop local mode, and the dashboard itself);
  `http(s)://…` calls a dashboard (task pods, notebook pods, a laptop working
  against Union). The HTTP API wraps the same SQLite module, so queries are
  written once. `STARGAZER_STORE_ROOT` picks the byte store the same way. Both
  ride into task pods through `_stargazer_env_vars()`, like `STARGAZER_OWNER`.
- **The dashboard's database is durable through the bucket**: restored at
  startup and replicated continuously by Litestream to
  `<STORE_ROOT>/users/<subject>/index/`.
- **TinyDB, the two storage modes and the Pinata remote go.** Pinata stays only
  where the asset-manager page uses it, until that page moves to the index
  (follow-up).
- **Not chosen:**
  - Union Artifacts as the index: Union-only. It could become a read-only
    projection for console lineage later.
  - One JSON object per asset as the query path: every query reads every
    record.
  - A SQLite file in the bucket that tasks write directly: concurrent writers
    race on one object.
  - Managed Postgres: the fallback if the dashboard can't own the index (Q1).

## Open questions

### Tenant behavior — gates Pieces 4–6

Each needs a throwaway app and task on the tenant (Piece 0). If Q1 fails, the
Union half switches to managed Postgres behind the same index interface.
Pieces 1–3 stand either way.

- [ ] **Q1. Can a task pod reach the dashboard?** Is
      `INTERNAL_APP_ENDPOINT_PATTERN` set in task pods (the SDK expects it in
      app pods), and does an app's internal URL answer from a task pod in the
      same project? Union's task-calls-app example uses
      `requires_auth=False`, a hint that it went through the public URL.
- [ ] **Q2. Do internal calls skip the login gate?** If not, task pods call the
      public URL with a bearer token minted from the platform key they already
      carry.
- [ ] **Q3. Does an internal request wake a scaled-to-zero app**, holding the
      request until the app is ready?
- [ ] **Q4. How long do the old and new dashboard versions overlap during
      `stargazer-users upgrade`?** Two live replicas means two copies of the
      database accepting writes, and the old copy's writes would be lost.
- [ ] **Q5. Is there a per-replica request cap** in front of apps, and do
      requests over it wait or fail? It matters when a large fan-out finishes
      at once.
- [ ] **Q6. Litestream under scale-to-zero:** restore-if-missing at startup,
      and a final sync at SIGTERM inside the `fserve` → launch script →
      uvicorn chain that plan 25 calls load-bearing.

### Decisions for the user

- [ ] **Q7. Byte-identical files with different metadata.** One row per CID
      means they collapse into one asset, and the second upload's metadata
      wins. TinyDB local mode already behaves this way. It's rare in genomics,
      where sample IDs end up inside the files, but possible for generic
      uploads. The alternative is a random row ID with the CID as a column.
- [ ] **Q8. Blob scope.** One shared `blobs/` (dedup across users) or
      `users/<subject>/blobs/` (ready for prefix-scoped permissions later,
      with shared data stored once per user).
- [ ] **Q9. Where shared data lives.** Bundles and references imported into
      each user's index on first use, or one shared catalog that every
      dashboard reads alongside its own.
- [ ] **Q10. The local path after `fetch()`.** Tasks read `asset.path` today.
      Either `fetch()` returns the path, or it sets an attribute that isn't
      serialized. The second keeps the 21 task files close to unchanged.
- [ ] **Q11. Backup records from day one?** Tasks could also write each row as
      a small JSON object next to its blob, so the index can always be rebuilt
      from the bucket and an outage or an upgrade overlap (Q4) loses nothing.
      It costs one extra write per asset. Defer unless Q4 or Q6 says
      otherwise.
- [ ] **Q12. Does `_owner` survive?** A per-user index already records whose
      an asset is.

### Details to confirm while building

- [ ] **Q13. Three-level CIDs.** Files over about 7.4 GiB
      (174 × 174 × 256 KiB) build a third tree level. Check one against
      Pinata or kubo (`ipfs add --only-hash --cid-version=1 --raw-leaves`)
      before relying on it for WGS-sized BAMs. Also confirm the empty file
      maps to the zero-byte raw leaf.
- [ ] **Q14. `File.from_local` to a `file://` destination** in local mode,
      outside a Flyte task context.
- [ ] **Q15. Laptop → Union ingest.** The laptop can't write to the bucket. The
      options are Union's data proxy (`create_upload_location`: scoped to a
      project, the control plane picks the key, so the row stores whatever
      URI comes back) or a signed URL minted by the dashboard. Unknown
      whether either does multipart uploads above 5 GB, which raw FASTQs
      will exceed.
- [ ] **Q16. The devbox.** Its app tier doesn't run (no Union auth), so
      remote runs there have no dashboard to index into. Union first, devbox
      later; see the ROADMAP's devbox app-tier item.

## Delivery

Two PRs, both from this branch:

1. **SDK** (Pieces 1–3): the CID module, the SQLite index, `Asset.file`, and
   the rewired storage client. Local mode works end to end. It doesn't depend
   on Piece 0. Union runs have no index until PR 2 lands, so the two should
   land close together.
2. **Union** (Pieces 0, 4–7): the dashboard index API, the HTTP client,
   Litestream, the tenant run and the docs. Shaped by Q1–Q6.

---

## Piece 0 — Tenant checks

- [ ] A throwaway app (`requires_auth=True`, `replicas=(0, 1)`) and task in
      one project. From the task: print `INTERNAL_APP_ENDPOINT_PATTERN`, call
      the internal URL, call the public URL with and without a bearer token,
      and call while the app is scaled to zero. Answers Q1–Q3.
- [ ] Redeploy the app while it's taking requests and record how long the old
      and new versions overlap. Answers Q4.
- [ ] Send 200 concurrent requests. Answers Q5.
- [ ] Litestream in the throwaway image: write, scale to zero, cold start, read
      back, and check the logs for the final sync at SIGTERM. Answers Q6.
- [ ] Record the results here and decide: dashboard index, or the Postgres
      fallback.

## Piece 1 — CID and the SQLite index (SDK)

### Tests first

- [ ] `GRCh38_TP53.fa`, `NA12829_TP53_R1.fq.gz` and `NA12829_TP53_R2.fq.gz`
      (already in `tests/fixtures/general/`) compute to their CIDs in
      `variant_calling_demo.yaml`. Covers one block and a multi-chunk tree.
- [ ] The empty file computes to
      `bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku` (the
      zero-byte raw leaf; Q13).
- [ ] Round trip: upsert a row, then query it back by its keyvalues.
- [ ] Exact match: a row missing one filter key, or holding a different
      value, doesn't match.
- [ ] A list-valued filter matches any of its values in one call.
- [ ] A companion lookup by `<asset_key>_cid` returns only that parent's
      companions.
- [ ] Upserting the same row twice leaves one row.
- [ ] Concurrent merges on one row keep every key.
- [ ] A read during a held write returns the last committed state without
      waiting.

Tests run against a SQLite file in a temp dir. No mocks.

### Implementation

- [ ] `src/stargazer/utils/cid.py`: streamed UnixFS CID with Pinata's
      parameters.
- [ ] `src/stargazer/utils/index.py`: the table, WAL mode, one write
      connection behind an `asyncio.Lock`, blocking calls kept off the event
      loop, and upsert / query / merge / delete.

## Piece 2 — Assets carry a `flyte.io.File`

- [ ] `Asset.path` → `Asset.file: File | None`, plus the local path per Q10.
- [ ] `update(path)`: compute the CID, upload the blob (skipped when it
      exists), upsert the row.
- [ ] `fetch()`: return the cached `<STARGAZER_LOCAL>/<cid>/<name>` if present,
      else download from `file`. Companions work as today.
- [ ] `specialize()` and `from_dict()` rebuild `file` from a row.
- [ ] Tasks, notebooks and the MCP marshaller follow the new field.

## Piece 3 — The storage client, rewired

- [ ] `STARGAZER_STORE_ROOT` and `STARGAZER_INDEX_URL` in `config.py`, with
      laptop defaults (`file://~/.stargazer/store`,
      `sqlite:///~/.stargazer/index.db`), forwarded by
      `_stargazer_env_vars()`.
- [ ] `LocalStorageClient` sends bytes through the store and metadata through
      the index backend. The Pinata remote, TinyDB and the two modes go, and
      `PINATA_JWT` leaves the task environments.
- [ ] Bundles: fetch from the gateway, verify the CID, put the file in the
      store, upsert the row. `_upsert_local` goes.
- [ ] `verify-stargazer` on the scRNA pipeline and GATK notebooks, locally.

## Piece 4 — The dashboard serves the index (Union)

- [ ] A router on the dashboard over the Piece 1 module: upsert, query, merge,
      delete. Rows validated through `build_asset()`.
- [ ] `HttpIndex` in the SDK: the same four calls, with retry and backoff.
- [ ] The dashboard passes its index URL to the notebook pods it launches, and
      the runs they start inherit it.

## Piece 5 — The dashboard's database survives scale-to-zero

- [ ] Litestream in the dashboard image: restore if missing at startup,
      replicate while running, final sync at SIGTERM, exec chain intact.
- [ ] Rows written before a scale-to-zero are there after the cold start.

## Piece 6 — Verify on the tenant

- [ ] The scRNA pipeline run from a notebook pod: files land in the bucket,
      rows land in the dashboard.
- [ ] A downstream task finds its upstream task's rows.
- [ ] A 20-way fan-out writes concurrently with no errors and no missing rows.
- [ ] `assemble()` from the notebook pod and from a laptop (public URL plus
      bearer token) returns the same rows.

## Piece 7 — Docs

- [ ] `docs/architecture/configuration.md`: the storage sections (modes,
      download flow, bundles) rewritten.
- [ ] `docs/architecture/types.md`: identity and the storage layer.
- [ ] `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md`: the index API and
      Litestream.
- [ ] Module docstrings on every module touched.
- [ ] ROADMAP: mark ✅, move to Complete, and add the follow-ups below.

## Follow-ups (not in this plan)

- `publish(asset)`: pin to IPFS on demand. The CID is already the asset's
  identity, so nothing about the asset changes.
- The asset-manager page on the index instead of Pinata. That also retires the
  TUS browser-upload item for uploads that go to the store.
- A read-only Artifacts projection of selected outputs, for console lineage
  and triggers.
- Data-aware caching: with Flyte's cache key set to the CID, check how much of
  that ROADMAP item is left.
