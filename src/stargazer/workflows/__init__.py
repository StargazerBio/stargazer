"""Flyte workflows for genomics pipelines."""

from stargazer.workflows.gatk_data_preprocessing import (
    prepare_reference,
    preprocess_sample,
)

from stargazer.workflows.germline_short_variant_discovery import (
    align_sample,
    call_variants_gvcf,
    germline_single_sample,
    germline_cohort,
    germline_from_gvcfs,
    germline_cohort_with_vqsr,
)

__all__ = [
    # GATK Best Practices data preprocessing workflows
    "prepare_reference",
    "preprocess_sample",
    # GATK Best Practices germline workflows
    "align_sample",
    "call_variants_gvcf",
    "germline_single_sample",
    "germline_cohort",
    "germline_from_gvcfs",
    "germline_cohort_with_vqsr",
]
