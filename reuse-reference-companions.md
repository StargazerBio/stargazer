---
title: reuse-reference-companions
status: backlog
priority: normal
created: 2026-11-01
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

- [ ] Test (workflow-level, isolated store): a reference with all three
      companions stored runs none of the index tasks; with only the
      `.fai`, runs the other two. Confirm it fails first on the current
      code because the tasks run.
- [ ] `prepare_reference` checks companions before each index task.
- [ ] Tasks tier, and the germline workflow on the devbox: second run
      shows no index tasks in the run's graph.
- [ ] Docs: the workflow's docstring; `docs/architecture/workflows.md` if
      it grows a convention ("workflows skip work the graph already has").
