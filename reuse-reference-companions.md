---
title: reuse-reference-companions
status: review
priority: normal
created: 2026-11-01
pr: 139
---

`prepare_reference` (`src/stargazer/workflows/gatk_data_preprocessing.py`)
runs `samtools_faidx`, `create_sequence_dictionary` and `bwa_mem2_index`
every time, whether or not the reference already has those companions.
A BWA-MEM2 index of a human genome takes hours. When the user has built
it before, or the reference's publisher put one on the public tier, the
workflow builds it again anyway. The asset graph already knows the answer
(`StorageClient.companions(cid)`), and the shipped pipeline doesn't ask.

This is the gap between what the docs want to say about the asset graph
and what's true: an index built once, by anyone who publishes it, serving
everyone who runs the pipeline. Opened from the docs revision that
introduces the asset graph and "collaboration without coordination".

Not ticket [[data-aware-caching]]: Flyte's cache is per project (inferred
there), keyed on a run's inputs, so it would at best skip a user's own
repeat, never use a publisher's index. Both can land; they don't overlap.

## Shape

- The workflow decides, not the tasks. Per the task rule, a task never
  checks whether its own work is needed; `prepare_reference` looks at the
  reference's companions (by their asset type and `tool`) and calls only
  the index tasks whose output is missing.
- Which companions count is `companions()`'s rule as it stands: the
  user's own first, then the caller's and the parent publisher's public
  ones.
- A partial set (say a `.fai` but no aligner index) builds only what's
  missing.

## Pieces

- [x] Test (workflow-level, isolated store): a reference with all three
      companions stored runs none of the index tasks; with only the
      `.fai`, runs the other two. Confirm it fails first on the current
      code because the tasks run.
- [x] `prepare_reference` checks companions before each index task.
- [x] Tasks tier, and the germline workflow on the devbox: second run
      shows no index tasks in the run's graph.
- [x] Docs: the workflow's docstring; `docs/architecture/workflows.md` if
      it grows a convention ("workflows skip work the graph already has").

## Plan

On `feat/reuse-reference-companions`.

`prepare_reference` asks `default_client.companions(ref.cid)` once and runs:

- `samtools_faidx` unless a companion has `asset == "reference_index"`;
- `create_sequence_dictionary` unless one has `asset == "sequence_dict"`;
- `bwa_mem2_index` unless, for each of the index's five extensions, a companion with `asset == "aligner_index"` and `aligner == "bwa-mem2"` is named `<fasta name><ext>`. An index missing a file, or a `bwa` index, doesn't count. The extensions become `BWA_MEM2_INDEX_EXTENSIONS` in `tasks/general/bwa_mem2.py`, which the task and the workflow share.

The workflow test is in the unit tier (`tests/unit/test_prepare_reference.py`), on the per-test store, with the three index tasks replaced by recorders in the workflow's module, since their tools aren't on the dev machine: what's asserted is which tasks the workflow calls. Cases: no companions (all three), all companions (none), only the `.fai` (the other two), an index short one file (bwa-mem2 only), a `bwa` index (bwa-mem2 only).

The tasks tier is unchanged by this (no task's behavior changes), so the Pieces' "tasks tier" line is the constant's move only.

## Evidence (2026-11-09)

- Unit tier: 285 passed. On the unchanged workflow 4 of the 5 new tests failed because all three index tasks ran (measured).
- Devbox: `pixi run pytest -m devbox tests/devbox/test_germline.py`, 2 passed in 2:43. Run `rv55z77sw9p6nt7r586l` on the branch has 8 actions and `gatk.prepare_reference` has no children; run `rjrhgvmgs28d6kwrtxmg` from `main` (2026-11-04) has 11, the three index tasks under `gatk.prepare_reference` (measured). The devbox's store held the reference's companions from earlier runs.
- Not driven: a publisher's index on the public tier, end to end.

## Verification recipe

REUSE-COMPANIONS: a germline run on a reference that already has its `.fai`, `.dict` and BWA-MEM2 index runs none of the index tasks.

1. With the devbox up and `FLYTE_IMAGE_REGISTRY=localhost:30000`, from the worktree (its `.flyte` linked): `pixi run pytest -m devbox tests/devbox/test_germline.py`. Run it twice on a fresh devbox, so the first run stores the companions.
2. List the latest germline run's actions with their tasks and parents:

   ```python
   import flyte, flyte.remote as r
   flyte.init_from_config(".flyte/config.yaml")
   run = "<run name from `flyte get run`>"
   for a in r.Action.listall(for_run_name=run):
       print(a.pb2.metadata.parent or "-", r.ActionDetails.get(run_name=run, name=a.name).task_name)
   ```

   Passes: no action is `gatk.samtools_faidx`, `gatk.create_sequence_dictionary` or `gatk.bwa_mem2_index`, and the test's cohort VCF checks pass. Fails as on `main`: the three are children of `gatk.prepare_reference`.

Related: [[board]].
