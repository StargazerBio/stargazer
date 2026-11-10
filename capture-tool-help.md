---
title: capture-tool-help
status: done
priority: low
created: 2026-11-01
pr: 144
---

Some tools Stargazer's tasks wrap have no captured help in the wiki ([[gatk]], [[tool-help]]): GATK's ApplyBQSR, CombineGVCFs, CreateSequenceDictionary and IndexFeatureFile, and bwa-mem2. Capture them with `raw/tool-help/generate_help_docs.sh` inside `gatk_env`'s image, link each from its tool's page, and update the tables.

The GATK help that is captured is from 4.6.1.0, while pixi.lock locks the image's `gatk4` to 4.6.2.0; recapture all of it from the image at the same time, so the help matches what the tasks run.

## Evidence (2026-11-09)

PR 144, on `docs/capture-tool-help`. All fourteen GATK tools captured with `generate_help_docs.sh` in the tasks tier's local `stargazer-gatk` build of `main`; every file's `Version:` line reads 4.6.2.0 (measured). bwa-mem2 has no `--help`, so its page is what its commands print with no arguments (2.2.1). The wiki lint passes.

## Outcome

PR 144 merged 2026-11-10 with no review comments. Shipped: the wiki's help for all fourteen wrapped GATK tools, recaptured at 4.6.2.0 from `gatk_env`'s image, and bwa-mem2's usage. Verified by each file's `Version:` line and the wiki lint (see Evidence). Nothing left.

Related: [[board]].
