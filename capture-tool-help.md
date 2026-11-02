---
title: capture-tool-help
status: backlog
priority: low
created: 2026-11-01
---

Some tools Stargazer's tasks wrap have no captured help in the wiki ([[gatk]], [[tool-help]]): GATK's ApplyBQSR, CombineGVCFs, CreateSequenceDictionary and IndexFeatureFile, and bwa-mem2. Capture them with `raw/tool-help/generate_help_docs.sh` inside `gatk_env`'s image, link each from its tool's page, and update the tables.

The GATK help that is captured is from 4.6.1.0, while the image installs bioconda's current `gatk4` unpinned; recapture all of it from the image at the same time, so the help matches what the tasks run.

Related: [[board]].
