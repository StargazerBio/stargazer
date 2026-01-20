"""Flyte workflows for genomics pipelines."""

from stargazer.workflows.germline_short_variant_discovery import (
    prepare_reference,
    align_sample,
    call_variants_gvcf,
    germline_single_sample,
    germline_cohort,
    germline_from_gvcfs,
)

__all__ = [
    # GATK Best Practices data preprocessing workflows (GATK + BWA)
    "preprocess_sample",
    "preprocess_cohort",
    "apply_bqsr_to_alignment",
    # GATK Best Practices data preprocessing workflows (Native GATK for mapped reads)
    "preprocess_mapped_sample_gatk",
    "preprocess_cohort_gatk",
    "gatk_apply_bqsr_to_alignment",
    # GATK Best Practices germline workflows
    "prepare_reference",
    "align_sample",
    "call_variants_gvcf",
    "germline_single_sample",
    "germline_cohort",
    "germline_from_gvcfs",
]
