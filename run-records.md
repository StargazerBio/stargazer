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

- Does `Action.inputs()` give back typed assets with their CIDs for a
  workflow's child actions, as read? The experiment below.
- Which actions' inputs count as the run's inputs: the leaves (assets a
  task took that no task in the run made) is the natural rule.
- Who makes the record: a button beside a finished run in the notebook,
  `dispatch()` on request, or every cluster run by default.
- Bundles: add an optional `query` per group of files to the manifest, so
  a bundle states what it's a snapshot of.

## Pieces

- [ ] Experiment, on the devbox: run `germline_short_variant_discovery`,
      then read every action's inputs and outputs through `flyte.remote`
      and check each asset's CID is there; confirm `with_runcontext`
      env vars reach a child task's pod.
- [ ] The record format, shared with bundles.
- [ ] Build a record from a finished run; store and publish it.
- [ ] `assemble()` answers from a snapshot when one is set.
- [ ] Replay from a notebook.
- [ ] Docs: `docs/architecture/types.md` (run records, snapshots) and the
      Asset Graph page.

Related: [[notebook-image-digest]], [[notebooks-in-git]], [[board]].
