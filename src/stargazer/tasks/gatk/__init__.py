"""
### GATK tasks for genomics workflows.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.tasks.gatk.apply_bqsr import apply_bqsr
from stargazer.tasks.gatk.base_recalibrator import base_recalibrator
from stargazer.tasks.gatk.create_sequence_dictionary import create_sequence_dictionary
from stargazer.tasks.gatk.haplotype_caller import haplotype_caller
from stargazer.tasks.gatk.mark_duplicates import mark_duplicates
from stargazer.tasks.gatk.merge_bam_alignment import merge_bam_alignment
from stargazer.tasks.gatk.sort_sam import sort_sam

__all__ = [
    "apply_bqsr",
    "base_recalibrator",
    "create_sequence_dictionary",
    "haplotype_caller",
    "mark_duplicates",
    "merge_bam_alignment",
    "sort_sam",
]
