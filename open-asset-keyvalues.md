---
title: Extra keyvalues on typed assets
status: doing
priority: high
created: 2026-10-09
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
- **Public assets are capped at Pinata's 10 keyvalues.** Pinata stores at most
  10 keyvalue pairs per file (stated by the user, 2026-10-09). `_owner` is
  always stamped, so a public asset has 9 keys for `asset`, its declared fields
  and any extras. The user's own index (SQLite, keyvalues stored as JSON text)
  has no such cap, so extras are limited only when a file goes to Pinata.
  Stargazer checks the count before calling Pinata, so the error is ours and
  clear rather than whatever Pinata does past the cap. Room left for extras on
  the public tier, per type:

  | Extras allowed on public | Types |
  |---|---|
  | 0 | `Alignment` (8 declared fields: already at the cap) |
  | 1 | `Variants`, `KnownSites` |
  | 2 | `AnnData` |
  | 3 | `VQSRModel` |
  | 5 | `R1`, `R2`, `ReferenceIndex`, `SequenceDict`, `AlignerIndex`, `BQSRReport`, `DuplicateMetrics` |
  | 6 | `AlignmentIndex`, `VariantsIndex` |
  | 7 | `Reference`, `KnownSitesIndex` |

- **The reserved `_` namespace is unchanged.** `build_asset()` still rejects
  `_`-prefixed keys. `_owner` is stamped onto the stored dict after
  `to_keyvalues()`, so it never reaches `keyvalues`.

## Steps

Tests come first in each step: run each new or changed test and confirm it
fails for the expected reason before implementing.

### 1. Round-trip extras on typed assets (`src/stargazer/assets/asset.py`)

- [ ] Tests in `tests/unit/test_asset.py`:
  - `Alignment.from_keyvalues({"asset": "alignment", "sample_id": "S1", "lane": "3"})`
    has `sample_id == "S1"` and `keyvalues == {"lane": "3"}`.
  - That asset's `to_keyvalues()` equals the input dict exactly.
  - An `Alignment` with `duplicates_marked=True` and `keyvalues={"lane": "3"}`
    gives `{"asset": "alignment", ..., "duplicates_marked": "true", "lane": "3"}`.
  - `keyvalues={"sample_id": "X"}` or `{"asset": "x"}` on an `Alignment` makes
    `to_keyvalues()` raise `ValueError`.
- [ ] `from_keyvalues()`: on a typed class, every key that isn't declared or
  `asset` goes into `keyvalues`.
- [ ] `to_keyvalues()`: on a typed class, start from `self.keyvalues`, raise on
  overlap with declared fields or `asset`, then write `asset` and the declared
  fields.
- [ ] Docstrings: the `keyvalues` attribute on `Asset` (now "extra keys" on typed
  subclasses), `to_keyvalues()`, `from_keyvalues()`.

### 2. Keep extras through `specialize()` (`src/stargazer/assets/__init__.py`)

- [ ] Replace `test_unknown_keyvalues_dropped_on_specialize` with one asserting
  the result is an `Alignment` with `keyvalues == {"custom_field": "custom_value"}`.
- [ ] No code change is expected beyond step 1. The fallback to a bare `Asset`
  on an unparseable declared value stays as it is.

### 3. Accept extras at upload and edit (`build_asset()`)

- [ ] Flip `tests/unit/test_assets_page.py::test_registered_key_unknown_field_raises`
  and the `"Unknown keys"` case in `tests/unit/test_assets_routes.py` (the
  `flowcell` upload): an undeclared key on a registered type now succeeds and is
  stored, and the route's response `keyvalues` contain it.
- [ ] `test_registered_key_malformed_value_raises` stays as it is: a declared
  non-`str` field that doesn't parse still raises.
- [ ] `build_asset()`: drop the unknown-keys check. `from_keyvalues()` now
  carries those keys.
- [ ] Docstrings: `build_asset()`, and the MCP `upload_file` / `update_file`
  tools in `src/stargazer/server.py` (an LLM reads these to decide how to call
  them: say registered types accept extra keys as strings).

### 4. Store and query through storage

- [ ] Test in `tests/utils/test_storage.py` (isolated store): an `R1` with
  `keyvalues["lane"] = "3"`, stored with `update()`. `assemble(asset="r1", lane="3")`
  returns exactly one asset, which is an `R1` with `keyvalues == {"lane": "3"}`.
  Expected to pass after step 1. The point is to prove the whole path to the
  index and back.

### 5. Enforce Pinata's 10-key cap (`src/stargazer/utils/pinata.py`)

- [ ] Unit test in `tests/utils/test_pinata.py` (that file makes no API calls,
  and nothing fakes `PinataClient`'s HTTP): the count helper passes a dict of
  exactly 10 keys and raises `ValueError` on 11, naming both numbers.
- [ ] Pinata-tier tests in `tests/pinata/test_client.py` (`-m pinata`, real API):
  - `upload()` of an `R1` with five extra keys succeeds and reads back with all
    10 keys.
  - `upload()` of an `Alignment` with one extra key raises the helper's
    `ValueError`, and nothing is stored.
  - `update_metadata()` that would take a record past 10 keys raises, and the
    record is unchanged. Pinata merges, so the total of existing and new keys
    is what counts.
- [ ] The asset-route tests in `tests/unit/test_assets_routes.py` replace
  `PinataClient` with a fake, so they can't see the check. Cover the page's
  400 by driving it in step 7 instead.
- [ ] One helper that checks a stamped keyvalues dict against `MAX_KEYVALUES = 10`,
  called from all three write paths after `_stamp_owner()`. For
  `update_metadata()`, count the union of the existing record's keys and the
  patch. It already looks the file up by CID first; check whether that response
  carries the current keyvalues before adding a second call.
- [ ] The asset page's `/assets/sign` and `/assets/update` turn that `ValueError`
  into a 400 with the message, like `build_asset()` errors today. Message in
  product terms, e.g. "Public assets can carry at most 9 fields; this one
  has 11."
- [ ] Docstrings on the three methods name the cap.

### 6. Asset page upload form (`app/templates/assets.html`)

- [ ] A registered type's upload form gets the same **+ Add field** key/value
  rows the custom form has, below the typed fields. Move the `kv-rows` block
  out of `custom-editor` so both modes share it, and have `collectKeyvalues()`
  merge the rows into the typed result, rejecting reserved keys and keys that
  are already declared fields.
- [ ] The edit form already allows adding keys and shows every key. Check only
  that saving an extra key on a typed record now succeeds.
- [ ] UI text in product terms ("Extra fields are stored as text"), with no
  implementation detail. A public upload over the cap shows step 5's error.

### 7. Verify on the real surfaces

- [ ] **Across pods (devbox).** In `tests/devbox/pod_tasks.py`, one task stores an
  `R1` with an extra key and returns it. A second task takes it as an input,
  which round-trips it through Flyte's type engine, and also finds it with
  `assemble(lane=...)`. Both copies must be `R1` with the extra key intact. Add
  the test to `tests/devbox/test_asset_storage.py` and a sub-feature line to
  `.claude/skills/verify-stargazer/features/devbox-asset-storage.md`. Run with
  the `verify-stargazer` skill.
- [ ] **MCP.** `upload_file` with `asset=alignment, lane=3`, then `query_files`
  with `lane=3`: the record comes back with `lane`.
- [ ] **Pinata.** Step 5's `-m pinata` tests pass. Optionally, send 11 keys
  straight to Pinata to answer the open question below.
- [ ] **Asset page over the cap.** A public upload with too many fields shows
  step 5's message, and nothing is stored.
- [ ] **Asset page.** Upload a typed asset with one extra field through the form,
  and see it in the detail view (needs the page running with storage
  configured; say so in the PR if it can't be driven).
- [ ] Full unit tier passes: `uv run --all-extras pytest`. `ruff --fix`.

### 8. Docs

- [ ] `docs/architecture/types.md`: the `keyvalues` row in the base-class table,
  the `__setattr__` paragraph (attributes are still strict, keyvalues aren't),
  **Catchall** (bare `Asset` is for unregistered kinds, not for extra fields),
  **Validation: `build_asset()`** (no unknown-keys check), **Specialization**.
- [ ] `docs/architecture/app.md` and `.opencode/reference/architecture/app_internals.md`:
  the asset page's upload form.
- [ ] `docs/guides/` and the assets tutorial notebook: grep for anything that
  says a typed asset rejects extra keys, or shows the escape hatch for that.
- [ ] Close this ticket: `status: done` and an Outcome section.

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

- What Pinata does past 10 keyvalues (rejects, or keeps some and drops the
  rest) is unchecked. Step 5 makes it moot for our own writes by checking
  first.
