# 25 — Workspace State on Object Storage

Make workspace persistence automatic and credential-free. The GitHub fork
stops being the storage backend and becomes an **opt-in path for graduating
notebooks** — publishing them upstream where they reach everyone else.

**Why.** Saving a notebook currently costs the user a fork of the upstream
repo plus a GitHub App install, before a single byte is persisted. That was
never a product decision: it is a workaround for missing persistent volumes.
`app/provision.py`'s docstring says so — *"Workspace state used to live on a
per-user PVC, but Flyte v2 doesn't support pod templates on AppEnvironments
yet."*

That premise is now false (`app_serde.py:361` serializes `pod_template` for
app envs), but a PVC is the wrong fix anyway: a per-user ReadWriteMany volume
is both more expensive and *slower* than pod-local disk. Object storage with
pod-local working state is cheaper and faster than either.

## What the user sees

Three tiers instead of today's two:

| Tier | Today | After |
|---|---|---|
| Run tutorials / workflows | Nothing required | Unchanged |
| Save your own notebooks | Fork + GitHub App install | **Nothing required** — saving just works |
| Graduate a notebook upstream | (same fork) | Opt-in: connect GitHub, PR it upstream |

## Settled design decisions

Recorded so they are not relitigated mid-build.

- **Object storage, not a PVC.** Hot state lives on pod-local disk; the
  object store is the durable copy. No idle volume cost, no RWX storage
  class, no volume lifecycle per user.
- **Directory sync, not a tarball.** `flyte.storage` exposes `get`/`put`
  with `recursive=True` (plus `put_stream`, `get_stream`, `exists`, `join`,
  over `S3`/`GCS`/`ABFS`). Each notebook stays an individually addressable
  object, which the dashboard depends on — see Piece 4. A tarball would turn
  every per-notebook header read into a download-and-unpack of the whole
  archive, and add pack/unpack CPU to cold start.
- **Keyed per notebook, not per user.** The one-modality-at-a-time rule caps
  one pod per *notebook*, not per user, so a user may legitimately run two
  notebooks at once. A single per-user object would let the second pod to
  scale down clobber the first's edits. Per-notebook keys make
  one-writer-per-object structural rather than a rule we rely on
  remembering.
- **The SIGTERM sync chain stays load-bearing.** State is still
  ephemeral-pending-upload, exactly as today. The `exec` discipline through
  `fserve` → launch script → uvicorn and
  `--timeout-graceful-shutdown 15` remain correctness-critical. (This is the
  one property a PVC would have bought us.)
- **Recoverable deletes come from bucket versioning**, replacing what git
  history provided.

## Scope

**In:** workspace notebook persistence, snapshot persistence, the launch
hydrate path, the sync path, the dashboard's listing/metadata reads, and
demoting the fork to opt-in.

**Out:** assets (already on Pinata), task/workflow data (already the Flyte
data plane), and the Union console work in
[`24_union_console_handoff.md`](./24_union_console_handoff.md).

---

## Piece 0 — Verify before building

- [ ] `flyte.storage.put(..., recursive=True)` and `get(..., recursive=True)`
      work **from inside an app pod**, not just a task pod. App pods take a
      different init path (`flyte.init_in_cluster()`, `app/init.py`); confirm
      the blob-store credentials are present there.
- [ ] The **admin** pod can read too — it needs per-notebook header reads for
      the dashboard listing (Piece 4). If it cannot, that path needs its own
      credential and a new entry in the deploy-secret contract.
- [ ] A storage backend is actually configured on **both** devbox and the
      target Union deployment, and they can be different URIs without a code
      change. Devbox diverges from production by habit — check
      `devbox_workarounds.md` and append anything new.
- [ ] Bucket **versioning** is available and enabled on the target bucket.
      Without it there is no recoverable-delete story at all.

---

## Piece 1 — The storage layer

A single module owning the key layout and the read/write primitives, so no
route composes URIs by hand.

### Tests first

- [ ] Round-trip: write a notebook, read it back byte-identical.
- [ ] List returns only that user's notebooks, never another user's.
- [ ] Key derivation rejects a slug that would escape the user's prefix
      (`../`, absolute paths, empty slug).
- [ ] Reading a missing notebook returns `None`, does not raise.
- [ ] Delete is idempotent — deleting twice succeeds.

### Implementation

- [ ] Key layout: `<root>/users/<user-key>/notebooks/<slug>.py` and
      `<root>/users/<user-key>/snapshots/<slug>.py`.
- [ ] **`<user-key>` must be the stable identifier.** Plan 24 Piece 3 decides
      whether that is the GitHub numeric id or the login; use whatever it
      lands on. A rename must not orphan someone's notebooks — this is the
      one place where getting it wrong is unrecoverable without a migration.
- [ ] Functions mirroring today's GitHub helpers so call sites change shape
      as little as possible: list, get, create (no-overwrite), update,
      delete, for workspace and snapshots.
- [ ] No-overwrite create, preserving the existing 409 collision rule that
      `/workspace/create` and `/workspace/copy` depend on.

---

## Piece 2 — Hydrate the pod at launch

- [ ] `launch-notebook.sh` replaces `git clone` with a recursive `get` of the
      notebook's object into `/workspace`.
- [ ] Drop `SG_POD_TOKEN` minting and the `GIT_ASKPASS` wiring from the
      launch path — there is no GitHub credential to protect any more.
- [ ] A missing object (brand-new notebook) hydrates as an empty workspace
      rather than failing the launch.
- [ ] Confirm cold-start latency does not regress. Notebook sources are
      kilobytes, so this should be strictly faster than a clone.

---

## Piece 3 — Sync on save and shutdown

- [ ] `/workspace/save` and the proxy's `lifespan` shutdown hook both write
      through the Piece 1 layer instead of `git add`/`commit`/`push`.
- [ ] **Do not touch the shutdown signal chain.** The `exec` discipline and
      `--timeout-graceful-shutdown 15` stay exactly as they are; only the
      verb at the end changes. Re-read the Working Branch & Sync section of
      `app_internals.md` before editing anything in this path.
- [ ] Keep sync **per notebook** — each pod writes only its own object, so
      one pod can never clobber another's.
- [ ] Verify an interrupted upload cannot leave a corrupt object. A single
      PUT is atomic per object; if the implementation ever chunks, it must
      complete-or-discard rather than partially overwrite.

---

## Piece 4 — Dashboard listing and metadata

This is the piece the tarball decision was made for.

- [ ] Tile listing reads from the object store instead of the GitHub API.
- [ ] The per-notebook `[tool.stargazer]` header fetches that seed each gear
      modal's `data-*` at page load become per-object GETs — same parallel,
      best-effort shape as today, one request per notebook. **This is why
      notebooks stay individual objects.**
- [ ] `/workspace/settings`, `/workspace/create`, `/workspace/delete`,
      `/workspace/snapshot` all move to the Piece 1 layer. The blob `sha`
      threading that `update_workspace_notebook` needs disappears.
- [ ] **Remove the opt-in gate from every save path.** `workspace_enabled`
      currently requires `fork_full_name` **and** `app_installed`; saving
      must no longer consult either. Audit every route that returns 403 on
      "not opted in" and confirm which of them still should.

---

## Piece 5 — Two couplings that break when the fork is optional

Both are non-obvious and will surface as bugs if missed.

- [ ] **`/workspace/copy` reads Workflows notebooks from the fork's source
      tree** (`get_repo_file`, path derived by stripping `IMAGE_WORKDIR` off
      `Notebook.path_in_image`). A user with no fork has no source tree to
      read. Re-point it at the notebook baked into the image, which is where
      that content actually lives.
- [ ] **Public snapshots currently travel *through* the fork.** Because a
      fork is a full copy of upstream, it already carries every merged public
      snapshot, and `list_snapshots(fork)` returns public and own together —
      `app_internals.md` is explicit that there is no separate
      upstream-listing path. Without a fork, that source is gone. Decide:
      ship public snapshots in the image like tutorials (simplest, and
      consistent with how every other shipped notebook reaches users), or
      build an upstream-listing path. Own snapshots move to object storage
      with everything else.

---

## Piece 6 — Demote GitHub to opt-in graduation

- [ ] Reframe the Workspace opt-in as **"Publish to GitHub"** — offered per
      notebook at the moment someone wants to graduate one, not as a gate on
      the whole Workspace section.
- [ ] Keep the existing fork + App-install handshake intact for this path;
      it is correct, it is just no longer mandatory. `installation_tokens.py`
      and the fork-scoped token model stay.
- [ ] Per AGENTS.md, the UI describes the feature in product terms — what
      publishing does for the user — not the fork/install mechanism.
- [ ] Confirm the freeze-then-publish story still reads coherently: a
      snapshot is frozen to object storage, and publishing pushes it to the
      fork for a PR upstream.

---

## Piece 7 — What gets deleted

Track the simplification; if none of this can go, the design drifted.

- [ ] `POST /workspace/pod-token` and the `SG_POD_TOKEN` capability, in
      `app/per_notebook.py`, `app/proxy.py`, and `launch-notebook.sh`.
- [ ] The `GIT_ASKPASS` wiring and token-free-remote handling.
- [ ] Fork-token plumbing on the *storage* paths. `installation_tokens.py`
      survives for Piece 6, but nothing in the save path should call it.
- [ ] The `workspace_enabled` gate on saving (not on publishing).

---

## Piece 8 — Docs

- [ ] `.opencode/reference/architecture/app_internals.md` — the Credential
      Model table, Workspace Opt-In, Working Branch & Sync, and Snapshots
      sections all describe the fork-as-storage design and all become wrong.
      This is the largest doc delta in the plan.
- [ ] `docs/architecture/app.md` and `docs/architecture/notebook.md`
      (Promotion Paths) — the human-facing companions.
- [ ] `app/provision.py` — the docstring's PVC rationale is now historical;
      replace it rather than leaving a stale premise.
- [ ] Module docstrings on every module touched, per the always-refresh rule.
- [ ] Mark ✅ and move to Complete in `ROADMAP.md`.
