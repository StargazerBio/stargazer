---
sources:
  - src/stargazer/config.py
  - src/stargazer/tasks/gatk/__init__.py
---

# GATK

The Broad Institute's Genome Analysis Toolkit, which most of Stargazer's germline tasks wrap. It's installed in `gatk_env`'s image from bioconda's `gatk4` (the comment above `gatk_env` in `src/stargazer/config.py`).

**The help was captured from GATK 4.6.1.0.** The image installs bioconda's current `gatk4`, unpinned, so when a flag matters, check `gatk --version` in the image against the help's `Version:` line.

| Tool | Help | Stargazer task |
|------|------|----------------|
| AnalyzeCovariates | [[gatk-analyzecovariates]] | none |
| ApplyBQSR | not captured | `apply_bqsr` |
| ApplyVQSR | [[gatk-applyvqsr]] | `apply_vqsr` |
| BaseRecalibrator | [[gatk-baserecalibrator]] | `base_recalibrator` |
| CombineGVCFs | not captured | `combine_gvcfs` |
| CreateSequenceDictionary | not captured | `create_sequence_dictionary` |
| GenomicsDBImport | [[gatk-genomicsdbimport]] | `joint_call_gvcfs` |
| GenotypeGVCFs | [[gatk-genotypegvcfs]] | `joint_call_gvcfs` |
| HaplotypeCaller | [[gatk-haplotypecaller]] | `haplotype_caller` |
| IndexFeatureFile | not captured | `index_feature_file` |
| MarkDuplicates | [[gatk-markduplicates]] | `mark_duplicates` |
| MergeBamAlignment | [[gatk-mergebamalignment]] | `merge_bam_alignment` |
| SortSam | [[gatk-sortsam]] | `sort_sam` |
| VariantRecalibrator | [[gatk-variantrecalibrator]] | `variant_recalibrator` |

Each task's module is `src/stargazer/tasks/gatk/<task>.py`. `joint_call_gvcfs` runs GenomicsDBImport, then GenotypeGVCFs, in one task, and needs the amd64 image (`IMAGE_PLATFORM` in `config.py` says why).

## Related

- [[tool-help]]: how the help is captured
- [[parabricks]]: the GPU equivalents of these tools
