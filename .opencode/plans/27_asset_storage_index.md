# 27 — Asset Storage on the Object Store, Indexed per User

Move asset bytes off Pinata and into object storage, and move the metadata
index into a SQLite database. On Union, each user's dashboard owns that
database: tasks and notebook pods upload files straight to the bucket and send
the dashboard one small row per asset. Locally the same database is a
file on disk, so local mode and the hosted deploy share one code path.
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
| Where task outputs go | Pinata, or local disk without a JWT | The object store: `file://` locally, the tenant bucket on Union |
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
  local machine can call the dashboard's public URL with the CLI's token.
- **A local machine can't reach the tenant bucket directly.** A read-only listing fell
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
  `<STORE_ROOT>/users/<subject>/assets/<cid>/<name>`. Keeping the filename in
  the key means a plain `File.download()` lands with the real extension. The
  subject is
  `STARGAZER_OWNER` (the Union subject, already forwarded into pods), or
  `local` when run locally without it. An upload whose file already exists
  skips the transfer.
- **`Asset.path` becomes a `flyte.io.File`** (Q10) at the stored location, so
  an asset passed between tasks points somewhere every pod can read.
  `update()` computes the CID, puts the bytes with `flyte.storage.put`, writes
  the index row, then sets `path = File(path=uri, name=name, hash=cid)`, which
  makes the CID Flyte's cache key too. Assigning a local `Path` to `path`
  wraps it in a File: an asset built from a file that was never uploaded.
- **`fetch()` returns the local path** (Q17). It downloads the asset to
  `<STARGAZER_LOCAL>/<cid>/<name>` and hardlinks every companion into the same
  directory, where GATK looks for `.fai`, `.dict` and `.bai`. Tasks read
  inputs as `bam = await alignment.fetch()`. An unstored local file comes back
  in place; an asset with only a CID is located through the index, then the
  public gateway.
- **Two tiers** (Q9). Private assets live in the user's store and index.
  Shared data is public data on Pinata's public network: anyone can read it,
  with no per-user restriction, and `_owner` records who uploaded it. Bundles
  and reference data live there. `assemble()` queries both and merges by CID;
  on a collision the user's own row wins. `fetch_bundle()` also registers each
  bundle file in the user's index (pointing at the gateway), so a fetched
  bundle is findable with or without a Pinata key. Promoting a private asset
  to public is a follow-up (`publish()`).
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
  holds one write connection behind a lock, so requests wait their turn. The
  lock is a `threading.Lock` taken inside the worker thread, not an
  `asyncio.Lock`: an asyncio lock belongs to one event loop, and a shared
  client is used from several (pytest-asyncio, notebooks). WAL mode lets reads run alongside writes without the
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
  read `X-User-*`. A local machine uses the public URL with the CLI's bearer token.
- **One setting picks the index backend.** `STARGAZER_INDEX_URL` is a SQLite
  file path (a `sqlite://` prefix is accepted; default `~/.stargazer/index.db`)
  opened directly by a local run and by the dashboard itself, or an `http(s)://`
  dashboard URL (task pods, notebook pods, a local run working against Union).
  The HTTP API wraps the same SQLite module, so queries are written once.
  `STARGAZER_STORE_ROOT` picks the byte store the same way (default
  `~/.stargazer/store`). Both ride into task pods through
  `_stargazer_env_vars()`, but only when set explicitly: a pod can't use a
  local run's defaults.
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
- [x] **Q19. The upgrade window.** Failing loudly covers writes that don't
      land, not Q4's window, where the old dashboard replica acknowledges a
      write after the new one has restored. Decided 2026-10-07:
      `stargazer-users upgrade` refuses while the user has runs going, for
      now; something better later.

### Details to confirm while building

- [ ] **Q13. Three-level CIDs.** Files over about 7.4 GiB
      (174 × 174 × 256 KiB) build a third tree level. Check one against
      Pinata or kubo (`ipfs add --only-hash --cid-version=1 --raw-leaves`)
      before relying on it for WGS-sized BAMs. Also confirm the empty file
      maps to the zero-byte raw leaf.
- [x] **Q14. `File.from_local` to a `file://` destination.** Moot: uploads use
      `flyte.storage.put` and then build the `File` directly, which works on
      a local root outside any task context (measured).
- [ ] **Q15. Local → Union ingest.** A local machine can't write to the bucket. The
      options are Union's data proxy (`create_upload_location`: scoped to a
      project, the control plane picks the key, so the row stores whatever
      URI comes back) or a signed URL minted by the dashboard. Unknown
      whether either does multipart uploads above 5 GB, which raw FASTQs
      will exceed.
- [ ] **Q16. The devbox.** Its app tier doesn't run (no Union auth), so
      remote runs there have no dashboard to index into. Union first, devbox
      later; see the ROADMAP's devbox app-tier item.
- [x] **Q17. The cache behind `File.download()`.** Flyte's `download()` has no
      cache (SDK source). Decided: `asset.path` always stays the stored File,
      and `fetch()` is the cached download, returning the local path with
      companions beside it (settled decisions above). Locally the cache
      hardlinks from the local store instead of copying.
- [x] **Q18. Public assets as `File`s.** `File.download()` can't read a
      gateway URL: flyte 2.10.7's HTTP filesystem fails with "Timeout context
      manager should be used inside a task" (measured). The storage client
      downloads `https://` paths with aiohttp instead. For local runs without a
      Pinata key, `fetch_bundle()` registers bundle files in the local index.
- [ ] **Q20. `VQSRModel.tranches_path` is a pod-local path.** It predates this
      plan: `variant_recalibrator` writes the tranches file's local path into
      metadata, so `apply_vqsr` in another pod can't read it. The tranches
      file should be its own companion asset. Not fixed here.
- [ ] **Q21. Remote runs submitted locally.** A pod can't read a
      local store or index, so the Execution tutorial's remote section
      (`flyte.run(audit_cohorts, …)`) can't work from a local session until Q15 and
      Q16 are settled. It needed a Pinata key before too. From a hosted
      notebook pod it works once Piece 4 is in.
- [x] **Q23. No Stargazer task could start on the tenant.** The `PINATA_JWT`
      secret didn't exist there, and a task declaring a missing secret fails
      in ~120 ms with no attempt (measured: the same trivial task succeeds
      without the declaration). Resolved 2026-10-07: the user added
      `PINATA_JWT` as an org-wide secret.
- [x] **Q22. `GRCh38_TP53.fa` was on Pinata's private network.** Resolved
      2026-10-07: the user deleted every private Pinata file, and the
      reference was re-uploaded to the public network from
      `tests/fixtures/general/` with its manifest keyvalues. Its CID matches
      the manifest, and all five bundle files are public (measured by CID
      lookup).

## Delivery

Two PRs, both from this branch:

1. **SDK** (Pieces 1–3): the CID module, the SQLite index, `Asset.path` as a
   `File`, and the rewired storage client. Local mode works end to end. It
   doesn't depend on Piece 0. Union runs have no index until PR 2 lands, so
   the two should land close together. The Execution tutorial's remote
   section needs a hosted notebook pod (Q21).
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

- [x] `GRCh38_TP53.fa`, `NA12829_TP53_R1.fq.gz` and `NA12829_TP53_R2.fq.gz`
      (already in `tests/fixtures/general/`) compute to their CIDs in
      `variant_calling_demo.yaml`. Covers one block and a multi-chunk tree.
- [x] The empty file computes to
      `bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku` (the
      zero-byte raw leaf; Q13).
- [x] Round trip: upsert a row, then query it back by its keyvalues.
- [x] Exact match: a row missing one filter key, or holding a different
      value, doesn't match.
- [x] A list-valued filter matches any of its values in one call.
- [x] A companion lookup by `<asset_key>_cid` returns only that parent's
      companions.
- [x] Upserting the same row twice leaves one row, with no warning.
- [x] Upserting a CID with different keyvalues replaces them and logs a
      WARNING naming the CID and the changed keys.
- [x] Concurrent merges on one row keep every key.
- [x] A read during a held write returns the last committed state without
      waiting.

Tests run against a SQLite file in a temp dir. No mocks.

### Implementation

- [x] `src/stargazer/utils/cid.py`: streamed UnixFS CID with Pinata's
      parameters. *(Also matches Pinata on a TUS upload — the pinata-marked
      test now compares CIDs — and on the 116 MB scRNA bundle files.)*
- [x] `src/stargazer/utils/index.py`: the table, WAL mode, one write
      connection behind a lock, blocking calls kept off the event loop, and
      upsert / query / get / merge / delete.

## Piece 2 — Assets carry a `flyte.io.File`

- [x] `Asset.path: Path | None` → `File | None`; a local `Path` assigned to
      it is wrapped in a File.
- [x] `update(path)`: compute the CID, upload to
      `users/<subject>/assets/<cid>/<name>` (skipped when it exists), and
      upsert the row with `_owner` stamped. Raises if either fails.
- [x] `fetch()`: returns the local path, companions beside it (Q17).
- [x] `specialize()` and `from_dict()` rebuild `path` from a row, or from a
      Pinata public record.
- [x] Tasks, notebooks and the MCP server follow the new type. Every task
      reads inputs as `path = await asset.fetch()`.

## Piece 3 — The storage client, rewired

- [x] `STARGAZER_STORE_ROOT` and `STARGAZER_INDEX_URL` in `config.py`, with
      local defaults (`~/.stargazer/store`, `~/.stargazer/index.db`),
      forwarded by `_stargazer_env_vars()` only when set explicitly.
- [x] `stargazer.utils.storage.StorageClient` replaces `LocalStorageClient`:
      private bytes through the store, metadata through the index. TinyDB
      (and the `tinydb` dependency) and the two modes go. The SDK no longer
      reads Pinata's private network; `PINATA_VISIBILITY` stops riding into
      pods and is read only by the asset-manager page. `PINATA_JWT` stays.
- [x] `query()` merges the user's index with Pinata's public index,
      deduplicated by CID, with the user's own row winning.
- [x] Bundles: `fetch_bundle` downloads by CID into the cache and registers
      each file in the index; `_upsert_local` goes.
- [x] Tests run against a per-test store and index; the fixture store is
      seeded once per session through the real client
      (`tests/fixtures/seed.py` replaces the TinyDB fixture DB). 405 passed,
      13 skipped — the same `gatk`/`bwa`/`samtools` skips as before: those
      tools aren't on the local PATH, so the GATK and alignment task
      tests have never run here.
- [x] `verify-stargazer` (2026-10-07, run `20261007-013105`): the scRNA
      pipeline notebook exports with exit 0 and `check_anndata.py` reads `ok`
      for both samples at every stage, raw through annotated. The assets,
      tasks and workflows tutorials export with exit 0. The Execution
      tutorial's local step (`audit_cohorts` in local mode) stores three
      linked `CohortSummary` assets that fetch back correctly; its remote
      section isn't driven (Q21). GATK notebooks unverified: tools absent.
      The skill now isolates the store and index too, and its anndata check
      reads the SQLite index.

## Piece 4 — The dashboard serves the index (Union)

- [x] `app/index_api.py` on the dashboard over the Piece 1 module: upsert,
      query, get, merge, delete. Rows are checked for shape only, not through
      `build_asset()`: they carry `_owner` and bundle keys that
      `build_asset()` rejects from users. Schema validation stays where assets
      are created.
- [x] `HttpIndex` in the SDK: the same calls over `httpx` (now a bounded core
      dependency), retrying connection errors and 5xx with backoff, raising
      once attempts run out. Tested end to end against the real router
      in-process, including a full upload-then-`assemble()`.
- [x] `/launch` gives notebook pods `STARGAZER_INDEX_URL` (the dashboard's
      in-cluster URL), `STARGAZER_STORE_ROOT` (the workspace root) and
      `STARGAZER_OWNER`; runs inherit them. Onboarding bakes the dashboard's
      own index path, store root and owner.
- [x] Q19: `stargazer-users upgrade` (and an onboarding re-run) refuse while
      the user has unfinished runs.

## Piece 5 — The dashboard's database survives scale-to-zero

- [x] Litestream in the dashboard image, installed the way Piece 0 did it (the
      v0.5.17 `.deb` for the build arch, via `with_commands`).
- [x] The dashboard's args are `exec python -m app.dashboard_launch`. The
      launcher writes the Litestream config, restores if missing, then execs
      `litestream replicate -exec "uvicorn …"`.
- [x] Two fixes found on the tenant (2026-10-07), both measured from the pod
      logs:
      - The first deploy crash-looped with `No module named
        app.dashboard_launch`. The code bundle carries only modules the
        deployer imported, and its `app/` shadows the installed package. The
        launcher is now in the dashboard's `include=`.
      - The second failed the restore with AccessDenied on
        `s3:GetBucketLocation`: Litestream looks up the region when none is
        given, and the pod role can't. The launcher now passes `AWS_REGION`,
        `AWS_DEFAULT_REGION` or `STARGAZER_STORE_REGION` (bakeable at
        deploy).
      The third deploy came up: `/index/query` answers `200 []` in 0.3 s
      through the front door, and the pod logs show Litestream compacting
      and snapshotting `index.db`.
- [x] Rows written before a stop are there after a cold start, on the real
      dashboard image: after the Piece 6 run, deactivating and reactivating
      the dashboard (51 s down, 24 s up) gave a fresh pod (`dashboard-00001-…`,
      empty disk), which served all 20 rows (measured 2026-10-07).

## Piece 6 — Verify on the tenant

Run 2026-10-07 in `u-pryce` (the test account's project), against its
redeployed dashboard
([run](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/u-pryce/runs/ugmd6kdxjpc684557t47)).
Real Stargazer tasks can't start on the tenant (Q23), so the run used
throwaway tasks on the dashboard image that declare no secret but call the
real SDK — `Asset.update()`, `Asset.fetch()`, `assemble()` — with
`STARGAZER_STORE_ROOT`, `STARGAZER_INDEX_URL` (the dashboard's in-cluster
URL) and `STARGAZER_OWNER` forwarded the way a notebook pod forwards them.
The harness isn't kept.

- [x] The real scRNA pipeline (`scrna_clustering_pipeline`) for both demo
      samples at once, after Q23 was resolved
      ([s1d1](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/u-pryce/runs/u9plg258jvg5pdsnl8x7),
      [s1d3](https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/u-pryce/runs/urm6nhrwrpfp5f856l2l)).
      Each run found its raw input through Pinata's public tier, downloaded
      it, and wrote all six stages to the bucket and the dashboard: 12 rows,
      each stamped `_owner`, stored under the owner's prefix, with a constant
      `n_obs` per sample across stages (8,506 and 8,322). Caveats: submitted
      locally with the environment a notebook pod forwards, not from
      a notebook pod; and run with the scRNA image fix from
      `fix/scrna-image-bio-extra` applied to the working tree (the image
      lacked `scikit-image` and `igraph`; that fix is its own branch).
- [x] Public gateways rate-limit. Repeated 116 MB downloads drew HTTP 429
      from both `dweb.link` and `gateway.pinata.cloud`. The account's
      dedicated gateway (`<name>.mypinata.cloud`) served them. Production
      should set `PINATA_GATEWAY` to it when deploying, so dashboards,
      notebook pods and the runs they start all use it.
- [x] A downstream task finds its upstream tasks' rows: a census pod's
      `assemble(asset="verify_note", run_tag=…)` found all 20, and every
      fetched file's contents matched. A reader pod fetched one by CID
      alone (index lookup, then the bucket).
- [x] A 20-way fan-out wrote concurrently with no errors and no missing rows.
      Every file landed at
      `s3://union-us-west-2-stargazerbio/stargazer/users/387300641116005877/assets/<cid>/<name>`.
- [~] From outside: the dashboard's front door (admin bearer token) returns
      the same 20 rows, each stamped `_owner=387300641116005877`. A local
      `assemble()` can't use the public URL yet: `HttpIndex` sends no token
      (Q21).

The 20 `verify_note` assets (`run_tag=p27-100126`) are still in the test
account's index and bucket. The test account's dashboard now runs this
branch.

## Piece 7 — Docs

- [x] `docs/architecture/configuration.md`: the storage sections (modes,
      download flow, bundles) rewritten.
- [x] `docs/architecture/types.md`: identity and the storage layer.
- [x] `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md`: the index API and
      Litestream.
- [x] Module docstrings on every module touched.
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
