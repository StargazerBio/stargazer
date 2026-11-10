---
title: untested-tasks
status: done
priority: normal
created: 2026-11-01
pr: 140
---

Tests for what has none: the tasks `bwa_mem`, `bwa_mem2_mem` and `index_feature_file`, and the workflow `scrna_clustering_pipeline`. The BWA index fixtures (`tests/fixtures/general/GRCh38_TP53.fa.{amb,ann,bwt,pac,sa}`) are kept as `bwa_mem`'s inputs.

The tasks tier runs in its images (`pixi run python cli/docker_task_tests.py`): it passed on [[pixi-layer-cache]]'s images, 20 tests in gatk's and 15 in scrna's.

## Plan

On `test/untested-tasks`. Tests only, all in the tasks tier, so each runs in its image.

- [x] `bwa_mem` (`tests/tasks/general/test_bwa.py`): paired fixture reads against the fixture FASTA and its BWA index beside it. The BAM's primary records (`samtools view -c -F 0x900`) are twice the R1 FASTQ's reads, its header carries the default `@RG` line, and `assemble(asset="alignment", sample_id=...)` returns it.
- [x] `bwa_mem2_mem` (`tests/tasks/general/test_bwa_mem2.py`): reference and reads stored, `bwa_mem2_index` run first so the index arrives as the reference's companions, as in the workflow. Same read count, and `reference_cid` and `r1_cid` are the inputs' CIDs.
- [x] `index_feature_file` (`tests/tasks/gatk/test_index_feature_file.py`): the known-sites VCF stored first, so its local copy has no `.idx` and GATK runs. The index is named `<vcf>.idx`, isn't empty, and is the VCF's only companion.
- [x] `scrna_clustering_pipeline` (`tests/tasks/scrna/test_scrna_clustering_pipeline.py`): the raw fixture stored as `stage="raw"`, run with `n_top_genes=200, max_pct_mt=80.0`. The result is `annotated` with `leiden` and `rank_genes_groups`, and every stage's AnnData is in the store. A sample with no raw AnnData raises naming it.
- [x] Tasks tier passes: `pixi run python cli/docker_task_tests.py`.

## Evidence (2026-11-09)

`pixi run python cli/docker_task_tests.py` on the four files: 6 passed in the gatk image, 2 passed in the scrna image (measured). Tests of existing behavior, so none was seen failing first.

## Outcome

PR 140 merged 2026-11-10 with no review comments. Shipped: tasks-tier tests for `bwa_mem`, `bwa_mem2_mem`, `index_feature_file` and `scrna_clustering_pipeline`. Verified by the tasks tier in its images (6 passed in gatk's, 2 in scrna's, measured 2026-11-09). Nothing left.

Related: [[board]].
