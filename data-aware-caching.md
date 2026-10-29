---
title: data-aware-caching
status: backlog
priority: normal
created: 2026-05-19
---

Turn on Flyte's task cache, keyed on what a task's assets contain, so a
workflow re-run only runs the tasks whose inputs are new. Workflows run the
queries (`assemble()`), so their inputs change as the index grows and they
stay uncached. Tasks take fixed assets, so when a query returns one more
sample, the fan-out re-runs only that sample's tasks, and only the steps
that gather across samples (`combine_gvcfs`, `joint_call_gvcfs`) run again.

**Today nothing caches.** Neither `gatk_env` nor `scrna_env` sets `cache=`,
`TaskEnvironment` defaults to `"disable"`, and no task overrides it, so every
run re-runs every task. Because tool outputs aren't byte-stable (GATK writes
a `Date=` into VCF headers; inferred), each re-run also uploads new CIDs and
adds rows to the index.

## How Flyte keys the cache

Read in Flyte 2.10.7 (`flyte/_internal/runtime/convert.py`), not measured:
the key is a hash of the inputs, the task name, its interface and a cache
version. A dataclass input is hashed as its whole msgpack bytes, unless its
literal carries a `hash`, which is used in place of the bytes. With
`cache="auto"`, the version is `FunctionBodyPolicy`: a hash of the task
function's own source.

## What breaks the key, and what to do

- **Metadata edits miss.** An `Asset` input is hashed with its `keyvalues`,
  which a user can edit on a stored file (and which carry `_owner`). The same
  bytes with a changed note miss. Key assets on their CID: set the literal's
  `hash` to the CID (or the CIDs of a list), so only content counts. Check
  that a typed field a task reads (`sample_id`, `duplicates_marked`) changes
  only along with the CID, or keep the fields it reads in the key.
- **`path` changes with where the bytes live.** A public asset's `path` is
  the IPFS gateway; the user's own copy of the same CID is
  `{store_root}/users/{owner}/assets/{cid}/{name}`. Keying on the CID covers
  this too.
- **Tool upgrades don't clear it.** `FunctionBodyPolicy` sees only the
  function body: not the image, so a GATK bump keeps serving old results, and
  not the helpers a task calls. Add a cache policy that hashes the image
  (`VersionParameters.image`) beside the function body.
- **Companions aren't inputs.** `fetch()` finds an asset's companions (the
  `.fai`, `.dict`, aligner index) by querying at run time. A hit returns a
  result that was right when it ran; a miss can pick up different
  companions. Leave it unless it bites, and see ticket
  `stale-companion-cache`.
- **Scope.** Union's cache is per project (inferred), and each user has their
  own, so one user's cached output, in their private storage, never reaches
  another. Confirm before relying on it.

## Pieces

- [ ] Assets carry their CID as the literal's hash when passed to a task.
- [ ] A cache policy over the function body and the image; `cache=` with it
      on `gatk_env` and `scrna_env`. Workflows keep `cache="disable"`.
- [ ] Tasks whose result isn't a function of their inputs (any that query
      or read the clock) opt out.
- [ ] Docs: how caching works in `docs/architecture/`, and when a task
      re-runs in the guides.

## Verification

On the devbox, then on Union as the test account:

- Run `germline_short_variant_discovery` twice with the same samples: the
  second run's per-sample tasks show as cache hits, and the index gains no
  rows.
- Add a sample and run again: only the new sample's tasks and the gather
  steps run.
- Edit an unrelated keyvalue on an input and run again: still hits.
- Change the image (a tool version) and run again: misses.
