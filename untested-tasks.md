---
title: untested-tasks
status: backlog
priority: normal
created: 2026-11-01
---

Tests for what has none: the tasks `bwa_mem`, `bwa_mem2_mem` and `index_feature_file`, and the workflow `scrna_clustering_pipeline`. The BWA index fixtures (`tests/fixtures/general/GRCh38_TP53.fa.{amb,ann,bwt,pac,sa}`) are kept as `bwa_mem`'s inputs.

The tasks tier runs in its images (`uv run --all-extras python cli/docker_task_tests.py`): it passed on [[pixi-layer-cache]]'s images, 20 tests in gatk's and 15 in scrna's.

Related: [[board]].
