"""Flyte workflows for genomics pipelines."""

from stargazer.workflows.gatk_data_preprocessing import (
    prepare_reference,
    preprocess_sample,
)

from stargazer.workflows.germline_short_variant_discovery import (
    germline_short_variant_discovery,
)

__all__ = [
    # GATK Best Practices data preprocessing workflows
    "prepare_reference",
    "preprocess_sample",
    # GATK Best Practices germline workflows
    "germline_short_variant_discovery",
]
