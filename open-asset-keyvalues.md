---
title: Extra keyvalues on typed assets
status: done
priority: high
created: 2026-10-09
pr: 25
---

Let a typed asset carry keyvalues its class doesn't declare. Declared fields
keep their types and their checks; any other key is kept as a plain string in
`keyvalues` and travels with the asset. An `Alignment` tagged `lane=3` stays an
`Alignment`, so every task that takes one can still be handed it.

**Why.** A registered type's schema is closed today. `build_asset()` rejects an
undeclared key, so a user who wants to record `library_id` on a BAM has one way
out: a made-up asset key (`my_alignment`), which comes back as a bare `Asset`.
That file then drops out of the typed world. MCP's `run_task` routes inputs by
`_asset_key`, so no task taking an `Alignment` is ever handed it. The fear is
that users who feel boxed in by the types use the bare-asset escape hatch
whenever they want an extra field, splitting one kind of file across many keys.
A closed type is what pushes them out. Typed fields with open extras give them
the freedom of bare keyvalues while keeping the guarantees tasks rely on.

Extra keys are also lost silently today, even without anyone uploading them.
Read from the code (2026-10-09), not run:

- `from_keyvalues()` on a typed class reads only declared fields, so
  `specialize()` drops any other key on a stored record
  (`tests/unit/test_specialize.py::test_unknown_keyvalues_dropped_on_specialize`
  pins this down).
- `to_keyvalues()` on a typed class writes only declared fields and ignores
  `self.keyvalues`, so an asset rebuilt from storage and stored again loses
  those keys.

The bare `Asset` stays the place for kinds of file nobody has registered yet.

## What changes

| | Today | After |
|---|---|---|
| Upload `asset=alignment, lane=3` (MCP, asset page) | `ValueError: Unknown keys for 'alignment': ['lane']` | Stored as an `Alignment` with `keyvalues == {"lane": "3"}` |
| Query a stored alignment that has `lane` | `Alignment`, `lane` dropped | `Alignment`, `lane` in `keyvalues` |
| `assemble(asset="alignment", lane="3")` | Can't match: the key can't be stored | Returns the `Alignment` |
| `aln.keyvalues` on a typed asset | Ignored | The asset's extra keys, round-tripped by `to_keyvalues()` / `from_keyvalues()` |
| `aln.lane = "3"` | `AttributeError` | Unchanged: attributes are declared fields only |
| `aln.update(path, lane="3")` | `AttributeError` | Unchanged: see Decisions |
| `build_asset({"asset": "variants", "sample_count": "three"})` | `ValueError` | Unchanged: declared fields still check their types |

## Decisions

- **Extras are strings, kept as-is.** They live in the existing `keyvalues:
  dict[str, str]` field, the same as on a bare `Asset`. No JSON decoding: the
  class has no type to decode into. If a class later declares that key, the
  stored value is parsed then, the same way bare records are promoted today.
- **Attributes and `update()` kwargs stay strict.** `__setattr__` keeps rejecting
  undeclared attributes, and `update(path, **kwargs)` still sets kwargs through
  it. Task code is where the declared fields get written, and a typo there
  (`sampel_id=`) should still fail loudly rather than become an extra key that
  no query matches. Extras in SDK code are explicit: `aln.keyvalues["lane"] = "3"`
  before `update()`.
- **Upload and metadata edit (`build_asset()`) accept extras.** This is the user
  surface where the closed schema bites. The cost: a misspelled declared field
  (`sampleid`) is stored as an extra key instead of being rejected. Accepted
  for now; see Deferred.
- **A declared field can't also be an extra.** `from_keyvalues()` splits a record
  so the two never overlap. If code puts a declared field or `asset` into
  `keyvalues` by hand, `to_keyvalues()` raises `ValueError` naming the
  attribute to set instead, rather than one silently winning.
- **New public files are capped at Pinata's 9 keyvalues.** Measured
  2026-10-13 against the real API (the user had said 10 on 2026-10-09):
  Pinata stores a new file with 9 keyvalues and refuses 10, `_owner`
  included. A plain upload gets a 400; a signed upload URL mints fine and
  the browser upload then fails with `"Failed to parse keyvalues as JSON"`.
  A metadata update has no cap: a merge reached 12 keys and all 12 were
  stored. So Stargazer checks the count on the two upload paths only, before
  sending anything, and doesn't invent a limit on updates that Pinata
  doesn't have. The user's own index (SQLite, keyvalues stored as JSON text)
  has no cap. `_owner` is always stamped, so a new public file has 8 keys
  for `asset`, its declared fields and any extras. Room left for extras on
  the public tier, per type:

  | Extras allowed on public | Types |
  |---|---|
  | none: can't be uploaded at all | `Alignment` (8 declared fields, so 10 keys with `asset` and `_owner`). Already broken on `main`, before this change: ticket `alignment-over-pinata-cap` |
  | 0 | `Variants`, `KnownSites` |
  | 1 | `AnnData` |
  | 2 | `VQSRModel` |
  | 4 | `R1`, `R2`, `ReferenceIndex`, `SequenceDict`, `AlignerIndex`, `BQSRReport`, `DuplicateMetrics` |
  | 5 | `AlignmentIndex`, `VariantsIndex` |
  | 6 | `Reference`, `KnownSitesIndex` |

- **The reserved `_` namespace is unchanged.** `build_asset()` still rejects
  `_`-prefixed keys. `_owner` is stamped onto the stored dict after
  `to_keyvalues()`, so it never reaches `keyvalues`.

## Steps

Tests come first in each step: run each new or changed test and confirm it
fails for the expected reason before implementing.

### 1. Round-trip extras on typed assets (`src/stargazer/assets/asset.py`)

- [x] Tests in `tests/unit/test_asset.py`:
  - `Alignment.from_keyvalues({"asset": "alignment", "sample_id": "S1", "lane": "3"})`
    has `sample_id == "S1"` and `keyvalues == {"lane": "3"}`.
  - That asset's `to_keyvalues()` equals the input dict exactly. (Only for a
    full record: `to_keyvalues()` writes every declared field, so the test
    input carries all of them, as every stored record does.)
  - An `Alignment` with `duplicates_marked=True` and `keyvalues={"lane": "3"}`
    gives `{"asset": "alignment", ..., "duplicates_marked": "true", "lane": "3"}`.
  - `keyvalues={"sample_id": "X"}` or `{"asset": "x"}` on an `Alignment` makes
    `to_keyvalues()` raise `ValueError`.
- [x] `from_keyvalues()`: on a typed class, every key that isn't declared or
  `asset` goes into `keyvalues`.
- [x] `to_keyvalues()`: on a typed class, start from `self.keyvalues`, raise on
  overlap with declared fields or `asset`, then write `asset` and the declared
  fields.
- [x] Docstrings: the `keyvalues` attribute on `Asset` (now "extra keys" on typed
  subclasses), `to_keyvalues()`, `from_keyvalues()`.

### 2. Keep extras through `specialize()` (`src/stargazer/assets/__init__.py`)

- [x] Replace `test_unknown_keyvalues_dropped_on_specialize` with one asserting
  the result is an `Alignment` with `keyvalues == {"custom_field": "custom_value"}`.
- [x] No code change is expected beyond step 1. The fallback to a bare `Asset`
  on an unparseable declared value stays as it is.

### 3. Accept extras at upload and edit (`build_asset()`)

- [x] Flip `tests/unit/test_assets_page.py::test_registered_key_unknown_field_raises`
  and the `"Unknown keys"` case in `tests/unit/test_assets_routes.py` (the
  `flowcell` upload): an undeclared key on a registered type now succeeds and is
  stored, and the route's response `keyvalues` contain it.
- [x] `test_registered_key_malformed_value_raises` stays as it is: a declared
  non-`str` field that doesn't parse still raises.
- [x] `build_asset()`: drop the unknown-keys check. `from_keyvalues()` now
  carries those keys.
- [x] Docstrings: `build_asset()`, and the MCP `upload_file` / `update_file`
  tools in `src/stargazer/server.py` (an LLM reads these to decide how to call
  them: say registered types accept extra keys as strings).

### 4. Store and query through storage

- [x] Test in `tests/utils/test_storage.py` (isolated store): an `R1` with
  `keyvalues["lane"] = "3"`, stored with `update()`. `assemble(asset="r1", lane="3")`
  returns exactly one asset, which is an `R1` with `keyvalues == {"lane": "3"}`.
  Expected to pass after step 1. The point is to prove the whole path to the
  index and back.

### 5. Check Pinata's 9-key cap on upload (`src/stargazer/utils/pinata.py`)

Rewritten after measuring the cap (see Decisions): 9, not 10, and uploads only.

- [x] Unit test in `tests/utils/test_pinata.py`: `_check_keyvalue_count()`
  passes 9 keys and raises `ValueError` on 10, naming both numbers.
- [x] Pinata-tier tests in `tests/pinata/test_client.py` (`-m pinata`, real API):
  - `upload()` of an `R1` with four extra keys succeeds and reads back with
    all 9 keys.
  - `upload()` of an `R1` with five extra keys raises the helper's
    `ValueError`, and nothing is stored.
  - Dropped: the `update_metadata()` test. Pinata doesn't cap updates.
- [x] The route tests' fake `PinataClient` runs the real check in
  `create_signed_upload_url()`, so `tests/unit/test_assets_routes.py` covers
  the page's 400. Two sign tests used an `Alignment`, which the check now
  refuses (ticket `alignment-over-pinata-cap`); they sign an `R1` instead.
- [x] `MAX_KEYVALUES = 9`, checked in `upload()` after `_stamp_owner()` and in
  `create_signed_upload_url()`.
- [x] `/assets/sign` turns the `ValueError` into a 400: "Public assets can
  carry at most 9 metadata fields, counting the asset type and owner; this
  one has 10."
- [x] Docstrings on both methods name the cap.

### 6. Asset page upload form (`app/templates/assets.html`)

- [x] A registered type's upload form gets the same **+ Add field** key/value
  rows the custom form has, below the typed fields. Move the `kv-rows` block
  out of `custom-editor` so both modes share it, and have `collectKeyvalues()`
  merge the rows into the typed result, rejecting reserved keys and keys that
  are already declared fields.
- [x] The edit form already allows adding keys and shows every key. Check only
  that saving an extra key on a typed record now succeeds.
- [x] UI text in product terms ("Extra fields are stored as text"), with no
  implementation detail. A public upload over the cap shows step 5's error.

### 7. Verify on the real surfaces

- [x] **Across pods (devbox).** In `tests/devbox/pod_tasks.py`, one task stores an
  `R1` with an extra key and returns it. A second task takes it as an input,
  which round-trips it through Flyte's type engine, and also finds it with
  `assemble(lane=...)`. Both copies must be `R1` with the extra key intact. Add
  the test to `tests/devbox/test_asset_storage.py` and a sub-feature line to
  `.claude/skills/verify-stargazer/features/devbox-asset-storage.md`. Run with
  the `verify-stargazer` skill.
- [x] **MCP.** `upload_file` with `asset=alignment, lane=3`, then `query_files`
  with `lane=3`: the record comes back with `lane`.
- [x] **Pinata.** Step 5's `-m pinata` tests pass (11 passed, 2026-10-13).
- [x] **Asset page over the cap.** A public upload with too many fields shows
  step 5's message, and nothing is stored.
- [x] **Asset page.** Upload a typed asset with one extra field through the form,
  and see it in the detail view (needs the page running with storage
  configured; say so in the PR if it can't be driven).
- [x] Full unit tier passes: `uv run --all-extras pytest`. `ruff --fix`.

### 8. Docs

- [x] `docs/architecture/types.md`: the `keyvalues` row in the base-class table,
  the `__setattr__` paragraph (attributes are still strict, keyvalues aren't),
  **Catchall** (bare `Asset` is for unregistered kinds, not for extra fields),
  **Validation: `build_asset()`** (no unknown-keys check), **Specialization**.
- [x] `docs/architecture/app.md` and `.opencode/reference/architecture/app_internals.md`:
  the asset page's upload form.
- [x] `docs/guides/` and the assets tutorial notebook: grep for anything that
  says a typed asset rejects extra keys, or shows the escape hatch for that.
- [x] Close this ticket after the PR merges: `status: done` and an Outcome section.

## Outcome

Merged in #25 (2026-10-13, `7f11457`).

**What shipped:**
- Typed assets keep undeclared keys as string extras in `keyvalues`, through
  `build_asset()` (MCP and the asset page), `specialize()`, the index,
  `assemble()` and Flyte task handoffs. Attributes and `update()` kwargs
  stay strict.
- Uploads to Pinata check its keyvalue cap first: 9, `_owner` included,
  measured against the real API. Metadata updates aren't capped by Pinata
  and aren't checked.
- The asset page's typed upload form takes extra fields.
- Docs: `types.md` (Extra keys), `configuration.md` (the cap), `app.md`,
  `mcp-server.md`, `app_internals.md`, and the verify-stargazer devbox
  feature map (`devbox-typed-extras`).

**How it was verified:** the unit, Pinata and devbox tiers, MCP over stdio,
and the asset page in Chrome. Details are under Verification below.

**What's left:**
- Ticket `alignment-over-pinata-cap`: no `Alignment` can be uploaded to
  Pinata. That was already true on `main`; it now fails with a clear message.
- The Deferred items below.
- An asset found with `assemble()` carries `_owner` among its extras. This
  was flagged in the PR and merged as is.

## Verification (2026-10-13)

- **Unit tier:** `uv run --all-extras pytest`, 410 passed. Each new or flipped
  test was run first against the code without the change and failed on the
  missing behavior.
- **Pinata tier:** `pytest -m pinata tests/pinata`, 11 passed, including the
  9-key upload and the refused 10-key upload.
- **Devbox:** `pytest -m devbox -rP tests/devbox/test_dashboard.py
  tests/devbox/test_asset_storage.py`, 5 passed in 94 s.
  `test_extra_keyvalue_travels_between_pods` ran `lane_round_trip`: the
  handed-in `R1` had `keyvalues == {"lane": …}`, and the one `assemble()`
  found had the same plus `_owner: devbox-user`.
- **MCP**, driven over stdio against an isolated store: `upload_file` with
  `asset=alignment, sample_id=S1, lane=3` returned a typed alignment (no
  generic-asset note) with `lane: "3"`, and `query_files({"lane": "3"})`
  returned it. The same drive against `main` failed `upload_file`
  (`is_error=True`), and the query came back empty.
- **Asset page**, run locally (`uvicorn app.admin_app:asgi_app` with
  `SG_STAND_IN_SUBJECT` and the Pinata key) and driven in Chrome on the
  Private tab:
  - An `r1` with five extra rows showed "Upload failed: An upload can carry
    at most 9 metadata fields, counting the asset type and owner; this one
    has 10." `/assets/sign` returned 400, and nothing was stored.
  - An `r1` with `lane=3` uploaded, and the detail view showed `lane 3`
    beside the declared fields.
  - From the edit form, adding `flowcell=X` saved. The Pinata record then
    held `asset, sample_id, mate_cid, sequencing_platform, lane, flowcell,
    _owner`.
  - The test file was deleted afterwards.
- **The cap message changed while driving the page.** It said "Public
  assets", but the page's Private tab hits the same limit, so it now says
  "An upload".

## Deferred

- **"Did you mean" for misspelled declared fields.** With unknown keys
  accepted, `sampleid` on an `Alignment` is stored as an extra key. A
  close-match check (`difflib`) in `build_asset()` could warn without blocking.
  Add it if typos show up in real records.
- **Extras following an asset through a pipeline.** `sort_sam` builds a new
  `Alignment` from its input's declared fields only, so `lane` on the input
  isn't on the output. Whether derived assets should inherit extras, and which
  ones, is a separate decision.
- **Watching the escape hatch.** Bare-asset keys in the index that shadow a
  registered type (`my_alignment`, `bam`) mean users are still being pushed
  out. Common bare keys for genuinely new kinds of file are candidates to
  register.

## Open questions

- ~~What Pinata does past 10 keyvalues.~~ Answered 2026-10-13 by sending
  files straight to the API: the cap is 9, and past it a new file is refused
  (see Decisions). Nothing is truncated.
