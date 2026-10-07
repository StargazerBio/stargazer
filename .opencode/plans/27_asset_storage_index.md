# 27 — Asset Storage on the Object Store, Indexed per User

Move asset bytes off Pinata and into object storage, and move the metadata
index into a SQLite database. On Union, each user's dashboard owns that
database: tasks and notebook pods upload files straight to the bucket and send
the dashboard one small row per asset. On a laptop the same database is a
local file, so local mode and the hosted deploy share one code path.
`assemble()` becomes a real query. Shared data stays public on Pinata, readable
by everyone and attributed to whoever uploaded it.

**Why.** Pinata does three jobs today: it stores the bytes, holds the keyvalue
index, and publishes public data. That makes it hard to move off. On Union it
means every intermediate BAM and h5ad leaves us-west-2 and comes back, under a
10 GiB per-file cap that a WGS BAM exceeds. The local fallback (TinyDB plus the
filesystem) is a second, separate mode, and it doesn't survive an ephemeral
pod. Union Artifacts would give a hosted index, but the open-source backend has
no artifact service. Splitting the three jobs lets each go to the right place:
bytes to whatever object store `flyte.storage` reaches, the index to SQLite we
own, and Pinata kept for public, shared data.

Isolation and security are out of scope: assumed solvable, and tracked on the
ROADMAP (**Per-user storage isolation**, **Org-wide platform key in every
pod**).

## What changes

| | Today | After |
|---|---|---|
| Where task outputs go | Pinata, or local disk without a JWT | The object store: `file://` on a laptop, the tenant bucket on Union |
| How `assemble()` finds them | Pinata's keyvalue filter, or a TinyDB scan | A SQL query against the user's index, merged with Pinata's public index |
| Shared data (bundles, references) | Pinata, public or private | Pinata's public network, attributed by `_owner` |
| Asset identity | IPFS CID from Pinata, or `local_<md5>` | IPFS CID computed locally, everywhere |
| An asset's file handle | `path: Path` | `path: flyte.io.File` |
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
- **Task pods reach apps at their internal address, without the login gate.**
  Measured with a throwaway app and tasks (Piece 0, results below): an app's
  internal URL is
  `http://<app-name>.<project>-<domain>.svc.cluster.local`, it answers task
  pods in the same project, it wakes the app from zero, and it carried a burst
  of 1,000 concurrent requests without a failure.
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
- **Private files are stored per user** (Q8):
  `<STORE_ROOT>/users/<subject>/assets/<cid>`. The subject is
  `STARGAZER_OWNER` (the Union subject, already forwarded into pods), or
  `local` on a laptop that doesn't set it. An upload whose file already exists
  skips the transfer.
- **`Asset.path` becomes a `flyte.io.File`** (Q10). Tasks work with it through
  the File API. `update()` computes the CID, uploads with
  `File.from_local(path, remote_destination=…/assets/<cid>, hash_method=cid)`
  so Flyte's cache key is the CID, then writes the index row. A row rebuilds
  the handle with `File.from_existing_remote(uri, file_cache_key=cid)`.
- **Local cache layout**: `<STARGAZER_LOCAL>/<cid>/<name>`, so a downloaded
  file keeps its real filename (GATK refuses inputs without it). How the cache
  sits behind `File.download()` is Q17.
- **Two tiers** (Q9). Private assets live in the user's store and index.
  Shared data is public data on Pinata's public network: anyone can read it,
  with no per-user restriction, and `_owner` records who uploaded it. Bundles
  and reference data live there. `assemble()` queries both and merges by CID;
  on a collision the user's own row wins. Promoting a private asset to public
  is a follow-up (`publish()`).
- **Same CID, new metadata is allowed and warned** (Q7). One row per CID: a
  re-upload whose keyvalues differ replaces them and logs a WARNING naming the
  CID and the keys that changed.
- **`_owner` is stamped everywhere** (Q12): on every private index row and on
  every public upload, from `STARGAZER_OWNER`. It matches Pinata, makes
  promotion to public a plain copy, and helps trace attribution errors and
  leaks.
- **A write that doesn't land fails the task** (Q11). If the index row hasn't
  committed after retries, `update()` raises, and the run is re-run. There are
  no backup records.
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
- **Pods call the dashboard at its internal address**,
  `http://<dashboard-app>.<project>-<domain>.svc.cluster.local`. Task pods
  don't get `INTERNAL_APP_ENDPOINT_PATTERN`, and `app_env.endpoint` in a task
  resolves to the public URL, so the address arrives through
  `STARGAZER_INDEX_URL`. (A task could also build it from
  `FLYTE_INTERNAL_PROJECT` and `FLYTE_INTERNAL_DOMAIN`, which every task pod
  has.) Internal requests carry no identity headers, so the index routes don't
  read `X-User-*`. A laptop uses the public URL with the CLI's bearer token.
- **One setting picks the index backend.** `STARGAZER_INDEX_URL=sqlite:///…`
  opens the file directly (laptop local mode, and the dashboard itself);
  `http(s)://…` calls a dashboard (task pods, notebook pods, a laptop working
  against Union). The HTTP API wraps the same SQLite module, so queries are
  written once. `STARGAZER_STORE_ROOT` picks the byte store the same way. Both
  ride into task pods through `_stargazer_env_vars()`, like `STARGAZER_OWNER`.
- **The dashboard's database is durable through the bucket**: restored at
  startup and replicated continuously by Litestream to
  `<STORE_ROOT>/users/<subject>/index/`.
- **TinyDB and the two storage modes go, and so does Pinata's private
  network**, since private data lives in the store. Pinata stays as the public
  tier, so `PINATA_JWT` stays in the task environments: Pinata needs it even
  to query public files.
- **Not chosen:**
  - Union Artifacts as the index: Union-only. It could become a read-only
    projection for console lineage later.
  - One JSON object per asset as the query path: every query reads every
    record.
  - A SQLite file in the bucket that tasks write directly: concurrent writers
    race on one object.
  - Managed Postgres: kept as the fallback in case the dashboard couldn't own
    the index. Piece 0 showed it can (Q1–Q3, Q5).

## Open questions

### Tenant behavior — gates Pieces 4–6

All six answered on the tenant in Piece 0 (details there). The dashboard can
own the index; the Postgres fallback isn't needed.

- [x] **Q1. Can a task pod reach the dashboard?** Yes, at the internal URL,
      `http://<app>.<project>-<domain>.svc.cluster.local`: 200 in 0.01s. Task
      pods don't get `INTERNAL_APP_ENDPOINT_PATTERN` (app pods do), and
      `app_env.endpoint` in a task resolves to the public URL, so the address
      has to be passed in or built from `FLYTE_INTERNAL_PROJECT`/`_DOMAIN`.
- [x] **Q2. Do internal calls skip the login gate?** Yes. The internal call
      reached the `requires_auth=True` app with no `X-User-*` or
      `Authorization` header. The public URL without a token got a 302 to the
      login page.
- [x] **Q3. Does an internal request wake a scaled-to-zero app?** Yes. After
      4 minutes idle (scale-down set to 60s) the request was held while a
      fresh replica started, then answered 3.05s after it was sent. That's
      for a light image; the dashboard image is heavier.
- [x] **Q4. How long do old and new versions overlap during a redeploy?**
      Barely. Polling every 250ms through the redeploy: 863 of 863 requests
      succeeded, traffic switched from v1 to v2 exactly once with no
      interleaving, and the last v1 answer came 0.12s after v2's process
      started (about 0.5s before v2's first answer). The real dashboard
      would restore its database before its process starts, so writes that
      reach the old replica between that restore and the switch would be
      lost. Small window, real risk; see Q11.
- [x] **Q5. Is there a per-replica request cap?** None hit. 200 concurrent
      2-second requests all ran at once (`max_inflight` 200, 2.86s wall).
      1,000 all succeeded, with up to 853 in flight, but took 22.6s: requests
      from one client got in at about 45 per second (cause not isolated).
      1,000 instant requests finished in 2.75s, about 360 per second. Excess
      load waits; it doesn't fail.
- [x] **Q6. Does Litestream restore at startup and sync at SIGTERM inside
      the `fserve` chain?** Yes, with no new IAM policy.
      - **Chain:** app args `exec python launch_probe.py`. The launcher
        writes the config, runs `litestream restore -if-db-not-exists
        -if-replica-exists`, then execs
        `litestream replicate -exec "uvicorn …"`.
      - **Setup:** `sync-interval: 1h`, so rows could only reach the bucket
        through the shutdown sync.
      - **Before shutdown:** 50 rows written, and the replica held only
        transaction 1.
      - **After scale-to-zero:** following 4 idle minutes, a fresh replica
        restored in 0.56s and had all 50 rows, every one written by the old
        replica. Transactions 2–3 were now in the bucket, and the wake took
        3.93s end to end.
      - **Startup with no replica:** exit 0 in 0.46s.
      - **Credentials:** Litestream used the pod's existing role. Extra S3
        access, if ever needed, is a policy on the shared
        `union-us-west-2-stargazerbio-userflyterole` in our own AWS account,
        with no Union step
        ([Union BYOC: enabling S3](https://www.union.ai/docs/v2/union/deployment/byoc/enabling-aws-resources/enabling-aws-s3.md)).

### Decisions for the user

Q7–Q12 decided 2026-10-07; the settled decisions above carry them.

- [x] **Q7. Byte-identical files with different metadata.** A legitimate
      outcome: one row per CID, the new keyvalues replace the old, and a
      WARNING is logged.
- [x] **Q8. File scope.** Per user, at `users/<subject>/assets/` for now.
- [x] **Q9. Where shared data lives.** On Pinata's public network, with no
      per-user restriction and only uploader attribution (`_owner`).
- [x] **Q10. The local path after `fetch()`.** `asset.path` is a
      `flyte.io.File`, which tasks handle through the File API. Where the
      cache sits is Q17.
- [x] **Q11. Backup records?** No. A task whose index write doesn't land fails
      loudly, and the run is re-run.
- [x] **Q12. Does `_owner` survive?** Yes: Pinata parity, cheap promotion to
      public, and a trail for attribution errors and leaks.
- [ ] **Q19. The upgrade window.** Failing loudly covers writes that don't
      land. It doesn't cover Q4's window, where the old dashboard replica
      accepts a write after the new one has already restored, so the write is
      acknowledged and then lost without any error. The cheapest guard is for
      `stargazer-users upgrade` to refuse while the user has runs going. The
      alternative is to accept the risk.

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
- [ ] **Q17. The cache behind `File.download()`.** Flyte's `download()` has no
      cache: with no argument it downloads to a fresh temp path every call,
      and with a path it downloads there again (SDK source). On a laptop that
      means copying out of the `file://` store on every read. Decide in
      Piece 2 how `<STARGAZER_LOCAL>/<cid>/<name>` sits in front of it, without
      ever leaving `asset.path` pointing at a pod-local file that another
      task can't read.
- [ ] **Q18. Public assets as `File`s.** A public asset's `path` would point at
      an IPFS gateway URL. Confirm `File.download()` reads that through
      `flyte.storage` (fsspec HTTP). Also, a laptop without a Pinata JWT can't
      query the public index, so bundles wouldn't show up in `assemble()`
      there. The bundle manifests could stand in.

## Delivery

Two PRs, both from this branch:

1. **SDK** (Pieces 1–3): the CID module, the SQLite index, `Asset.path` as a
   `File`, and the rewired storage client. Local mode works end to end. It
   doesn't depend on Piece 0. Union runs have no index until PR 2 lands, so
   the two should land close together.
2. **Union** (Pieces 4–7): the dashboard index API, the HTTP client,
   Litestream, the tenant run and the docs. Q1–Q6 are answered (Piece 0).

---

## Piece 0 — Tenant checks

Run 2026-10-06 (local time) in `flytesnacks/development`: a throwaway FastAPI
app `sg-probe-index` (`requires_auth=True`, `replicas=(0, 1)`, 60s
scale-down) and tasks on the same image, driven from the CLI. The app was
deactivated afterwards. The harness itself isn't kept; the results and run
links below are the record. The parts it prototyped that ship are built in
their real modules: the Litestream image layer and launcher in the dashboard
(Piece 5), and the CID code in `src/stargazer/utils/cid.py` (Piece 1).

- [x] From a task: print the environment, call the internal URL, call the
      public URL without a token. Answers Q1–Q2.
      ([run](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/flytesnacks/runs/uh9mlcxmzjglrzs5skk6))
- [x] From a task: call, sleep 240s, call again. Answers Q3.
      ([run](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/flytesnacks/runs/uttvm5wpqr6p5krwr6hg))
- [x] Redeploy the app (v1 → v2) while polling it every 250ms. Answers Q4.
- [x] From a task: 200 and 1,000 concurrent 2s requests, and 1,000 instant
      ones. Answers Q5.
      ([200](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/flytesnacks/runs/udkjvt5mmmrpcg2cs42c),
      [1,000](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/flytesnacks/runs/urxq89c68lbkt77r5wq5),
      [1,000 instant](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/flytesnacks/runs/uvx97lkd6hf4ksr5qkpv))
- [x] Litestream v0.5.17 in the throwaway image, `sync-interval: 1h`: write,
      let it scale to zero, wake it, read back. Answers Q6. The replica prefix
      (`stargazer/_probe/plan27/`) was deleted afterwards.
- [x] Decision: the dashboard owns the index. The Postgres fallback isn't
      needed.

| Check | Result |
|---|---|
| Internal pattern (app pod) | `http://{app_fqdn}.flytesnacks-development.svc.cluster.local` |
| Same in task pod | Not set. `app_env.endpoint` resolves to the public URL |
| Task → internal URL | 200 in 0.01s, no `X-User-*` or `Authorization` headers |
| Task → public URL, no token | 302 to the tenant login page |
| Internal call to an app idle 4 min | Fresh replica; answered 3.05s after the request |
| 200 × 2s concurrent | All 200 OK, all in flight at once, 2.86s wall |
| 1,000 × 2s concurrent | All 200 OK, up to 853 in flight, 22.6s wall |
| 1,000 instant | All 200 OK, 2.75s wall |
| Redeploy under polling | 863/863 OK, one clean v1→v2 switch, v1 answered 0.12s past v2's start |
| Litestream restore, no replica | Exit 0 in 0.46s |
| Litestream across scale-to-zero (1h interval) | 50/50 rows restored in 0.56s; only the SIGTERM sync could have uploaded them |

Not tested, and outside this plan: whether a pod in another project can reach
an app's internal URL, and whether a forged `X-User-Subject` sent there
reaches the app unchanged. The front door overwrites those headers, and the
internal path skips the front door. Tracked on the ROADMAP.

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
- [ ] Upserting the same row twice leaves one row, with no warning.
- [ ] Upserting a CID with different keyvalues replaces them and logs a
      WARNING naming the CID and the changed keys.
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

- [ ] `Asset.path: Path | None` → `File | None`. Tasks get local copies
      through the File API, with the cache placed per Q17.
- [ ] `update(path)`: compute the CID, upload to
      `users/<subject>/assets/<cid>` (skipped when it exists), and upsert the
      row with `_owner` stamped. Raise if the row hasn't committed after
      retries.
- [ ] `fetch()`: downloads companions as today, through the cache.
- [ ] `specialize()` and `from_dict()` rebuild `path` from a row, or from a
      Pinata public record (Q18).
- [ ] Tasks, notebooks and the MCP marshaller follow the new type.

## Piece 3 — The storage client, rewired

- [ ] `STARGAZER_STORE_ROOT` and `STARGAZER_INDEX_URL` in `config.py`, with
      laptop defaults (`file://~/.stargazer/store`,
      `sqlite:///~/.stargazer/index.db`), forwarded by
      `_stargazer_env_vars()`.
- [ ] `LocalStorageClient` sends private bytes through the store and metadata
      through the index backend. TinyDB and the two modes go. Pinata becomes
      the public tier only, so `PINATA_VISIBILITY` and private signed-URL
      downloads go and `PINATA_JWT` stays.
- [ ] `query()` merges the user's index with Pinata's public index,
      deduplicated by CID, with the user's own row winning.
- [ ] Bundles stay on Pinata's public network. `fetch_bundle` downloads them
      by CID into the cache, and `_upsert_local` goes (laptops without a JWT:
      Q18).
- [ ] `verify-stargazer` on the scRNA pipeline and GATK notebooks, locally.

## Piece 4 — The dashboard serves the index (Union)

- [ ] A router on the dashboard over the Piece 1 module: upsert, query, merge,
      delete. Rows validated through `build_asset()`.
- [ ] `HttpIndex` in the SDK: the same four calls, with retry and backoff.
- [ ] The dashboard passes its index URL to the notebook pods it launches, and
      the runs they start inherit it.

## Piece 5 — The dashboard's database survives scale-to-zero

- [ ] Litestream in the dashboard image, installed the way Piece 0 did it (the
      v0.5.17 `.deb` for the build arch, via `with_commands`).
- [ ] The dashboard's args change from bare `uvicorn …` to
      `exec python <launcher>`. The launcher writes the Litestream config,
      restores if missing, then execs
      `litestream replicate -exec "uvicorn …"`. This is the chain Piece 0
      proved, and it keeps Litestream as the process `fserve` signals.
- [ ] Rows written before a scale-to-zero are there after the cold start, on
      the real dashboard image.

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

- `publish(asset)`: promote a private asset to the public tier by uploading
  it to Pinata's public network with its keyvalues and `_owner`. The CID is
  already the asset's identity, so nothing about the asset changes.
- The asset-manager page on the index instead of Pinata. That also retires the
  TUS browser-upload item for uploads that go to the store.
- A read-only Artifacts projection of selected outputs, for console lineage
  and triggers.
- Data-aware caching: with Flyte's cache key set to the CID, check how much of
  that ROADMAP item is left.
