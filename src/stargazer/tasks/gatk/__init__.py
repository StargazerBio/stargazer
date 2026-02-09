"""GATK tasks for genomics workflows."""

from stargazer.tasks.gatk.apply_bqsr import applybqsr
from stargazer.tasks.gatk.base_recalibrator import baserecalibrator
from stargazer.tasks.gatk.create_sequence_dictionary import create_sequence_dictionary
from stargazer.tasks.gatk.mark_duplicates import markduplicates
from stargazer.tasks.gatk.merge_bam_alignment import mergebamalignment
from stargazer.tasks.gatk.sort_sam import sortsam

__all__ = [
    "applybqsr",
    "baserecalibrator",
    "create_sequence_dictionary",
    "markduplicates",
    "mergebamalignment",
    "sortsam",
]
