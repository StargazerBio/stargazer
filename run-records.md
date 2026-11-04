---
title: run-records
status: maybe
priority: normal
created: 2026-11-02
---

A reproducibility artifact is the record of a run, not a notebook. A
notebook that asks the graph questions (`assemble(build=..., sample_id=...)`)
is code: reusable, versioned in git (ticket `notebooks-in-git`). One run of
it has fixed inputs, an exact image and fixed outputs, and that record is
data, so it belongs in the asset graph: a small file with its own CID,
publishable, citable in a paper, which outputs link back to (`run_cid`,
the usual `<asset>_cid` convention). Replaying it reruns the same code on
the same image with every query answered from the record.

The lock-file analogy: a workflow notebook is a library (it declares what
it wants), and a run record is the lock file of one application of it (what
that run resolved to).

**Bundles are the same thing without the run:** a snapshot in time of a
query's result. A bundle today is a YAML list of files by CID with their
keyvalues; the query that picked them is implicit. A run record's inputs
are a bundle produced by a run instead of curated by hand. One format for
both.

## Decided (2026-11-02)

- **Rely on Flyte's run infrastructure; don't rebuild it.** Flyte already
  keeps each run and each action's inputs and outputs, the code it ran and
  its console URL. A run record points at that and adds only what Flyte
  doesn't have.
- Notebooks stay code in git; run records are data in the graph.

## What Flyte already has

Read in Flyte 2.10.7 (`flyte/remote/_run.py`, `_action.py`), not measured:

- `Run` and `Action` expose `inputs()` and `outputs()`. A typed `Asset`
  crosses a task boundary as its dataclass fields, CID included, so the
  assets every task actually took and made should be readable back from a
  finished run, including the ones a workflow resolved with `assemble()`
  inside its own pod.
- `Run.download_code()` / `code_bundle()`: the code the run executed (a
  source tarball, or a cloudpickle when launched from a notebook).
- The run's name and console URL; runs stay in the owner's project.
- `flyte.with_runcontext(env_vars=...)` passes environment variables to
  every task in a run.

## What a run record adds

- **The image digests.** Flyte records image tags, which name a recipe,
  not bytes (ticket `notebook-image-digest`). The record carries the
  notebook pod's digest and, if it's cheap, each task image's, resolved
  from the registry.
- **The queries and what they resolved to,** in the bundle format, built
  from the run's action inputs: each input asset by CID with its
  keyvalues.
- **The outputs** by CID.
- **The notebook source:** its `repo@commit:path` when it came from git;
  otherwise the file itself, stored as an asset, with its CID.
- **The Flyte run's name and URL**, for whoever can reach it. A run's own
  record stays private in its project; the run record is the public part.
- Optionally the notebook's HTML export, the narrative and plots as they
  were.

It's a file, so lists live in its bytes and the public tier's 9-keyvalue
cap doesn't bind.

## Replay

Open the notebook source the record names, launch on its image digest
(build or pull, ticket `notebook-image-digest`), and run with
`env_vars={"STARGAZER_SNAPSHOT": <record cid>}`. `assemble()` honours it:
with a snapshot set, a query returns the snapshot's matching assets instead
of searching the index. Tasks on the cluster get it from Flyte like any
env var, so a workflow's own queries replay too. `fetch_bundle()` and
replay share the snapshot reader.

## Open questions

- A task's own lookups are queries too, and no action's inputs show them:
  `Asset.fetch()` finds an asset's companions with
  `StorageClient.companions(cid)`, an index query on `companion_of`. In the
  experiment run every companion a task fetched was made in the run, but a
  run on an already-indexed reference resolves its index files that way
  and the record wouldn't see them. Replay has to answer `companions()` from
  the snapshot as well as `assemble()`, and the record needs the companions
  of each input it lists.
- Who makes the record: a button beside a finished run in the notebook,
  `dispatch()` on request, or every cluster run by default.
- Bundles: add an optional `query` per group of files to the manifest, so
  a bundle states what it's a snapshot of.

## Pieces

- [x] Experiment, on the devbox: run `germline_short_variant_discovery`,
      then read every action's inputs and outputs through `flyte.remote`
      and check each asset's CID is there; confirm `with_runcontext`
      env vars reach a child task's pod. Results below.
- [ ] The record format, shared with bundles.
- [ ] Build a record from a finished run; store and publish it.
- [ ] `assemble()` answers from a snapshot when one is set.
- [ ] Replay from a notebook.
- [ ] Docs: `docs/architecture/types.md` (run records, snapshots) and the
      Asset Graph page.

## Experiment (2026-11-04, devbox, Flyte 2.12.4)

Measured. `tests.devbox.pod_tasks.seed` stored the TP53 fixtures (run
`rhrfd5k55wndz69plhxj`), then `germline_short_variant_discovery(build="GRCh38",
sample_ids=["NA12829"], cohort_id="cohort-11c7617a")` ran with the devbox
storage settings plus `STARGAZER_SNAPSHOT_PROBE=probe-1234` in
`with_runcontext(env_vars=...)` (run `rgsfvctgsxkqghfsshls`, succeeded, 11
actions).

- **Env vars reach every pod.** A watcher polling the run's pods
  (`kubectl get pods -n flyte -o json`, the probe's value per pod) saw
  `probe-1234` in all 11: the workflow, its two sub-workflows
  (`prepare_reference`, `preprocess_sample`) and every task under them.
- **Every asset crosses with its CID, at every depth.** All 11 actions'
  inputs and outputs read back through `flyte.remote.Action.listall` +
  `details().inputs()/outputs()`, each asset with its CID, a list of assets
  (`bwa_mem2_index`'s five `AlignerIndex`es, `joint_call_gvcfs`'s `gvcfs`)
  included.
- **The leaves rule needs "childless actions only".** `prepare_reference`
  returns the reference it queried, so "inputs no action output" drops the
  reference and leaves only R1 and R2. Taking outputs only from actions
  with no children gives exactly the three assets the queries resolved,
  which are `variant_calling_demo`'s CIDs (`bafkreib6vj3…` reference,
  `bafybeia3lsm…` R1, `bafybeihd3nq…` R2). The seed run's outputs match
  the bundle's CIDs too.
- **Decode with the task's declared types.** `inputs()`/`outputs()` give
  look-alike dataclasses Flyte builds from the schema
  (`flyte.types._type_engine`), named like the asset class, with its fields
  but no `to_keyvalues()` and no `asset` key. `typed_inputs({"r1": R1, ...})`
  gives real Stargazer assets with full keyvalues (`_owner` included), but
  the type must match the declaration: `r2` is `R2 | None` on
  `bwa_mem2_mem`, and decoding it as `R2` silently returned an empty R2
  (no CID, no keys). The registry's signatures can supply the types.
- `Action.task_name` is `None` on every action; the task's name is
  `details().metadata.task.id.name` (`gatk.bwa_mem2_mem`). The root
  action's `details().code_bundle` names the run's code tarball.

The reader, run as `uv run --all-extras python read_actions.py <run>` from
the repo root with `.flyte/config.yaml` pointing at the devbox:

```python
import json, sys
import flyte, flyte.remote as remote
from stargazer.config import PROJECT_ROOT

flyte.init_from_config(PROJECT_ROOT / ".flyte" / "config.yaml", root_dir=PROJECT_ROOT)

def describe(v):
    if isinstance(v, list):
        return [describe(x) for x in v]
    if hasattr(v, "cid") and hasattr(v, "keyvalues"):
        return {"type": type(v).__name__, "cid": v.cid, "keyvalues": v.keyvalues}
    return v

report = []
for action in remote.Action.listall(for_run_name=sys.argv[1]):
    d = action.details()
    report.append({
        "action": action.name,
        "task": d.metadata.task.id.name,
        "parent": action.parent_name,
        "inputs": {k: describe(v) for k, v in d.inputs().items()},
        "outputs": [describe(v) for v in d.outputs()],
    })
print(json.dumps(report, indent=1, default=repr))
```

Related: [[notebook-image-digest]], [[notebooks-in-git]], [[board]].
