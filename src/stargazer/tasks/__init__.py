"""
### Stargazer tasks for bioinformatics workflows.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.tasks.general.samtools import samtools_faidx
from stargazer.tasks.general.bwa import bwa_index, bwa_mem
from stargazer.tasks.gatk.create_sequence_dictionary import create_sequence_dictionary

# GATK tasks
from stargazer.tasks.gatk.base_recalibrator import base_recalibrator
from stargazer.tasks.gatk.apply_bqsr import apply_bqsr
from stargazer.tasks.gatk.mark_duplicates import mark_duplicates
from stargazer.tasks.gatk.sort_sam import sort_sam
from stargazer.tasks.gatk.merge_bam_alignment import merge_bam_alignment
from stargazer.tasks.gatk.haplotype_caller import haplotype_caller
from stargazer.tasks.gatk.combine_gvcfs import combine_gvcfs
from stargazer.tasks.gatk.genomics_db_import import genomics_db_import
from stargazer.tasks.gatk.joint_call_gvcfs import joint_call_gvcfs
from stargazer.tasks.gatk.variant_recalibrator import variant_recalibrator
from stargazer.tasks.gatk.apply_vqsr import apply_vqsr

__all__ = [
    # Reference indexing
    "samtools_faidx",
    "create_sequence_dictionary",
    "bwa_index",
    "bwa_mem",
    # Data preprocessing (GATK)
    "sort_sam",
    "mark_duplicates",
    "merge_bam_alignment",
    # BQSR (Base Quality Score Recalibration)
    "base_recalibrator",
    "apply_bqsr",
    # GVCF processing
    "haplotype_caller",
    "joint_call_gvcfs",
    "combine_gvcfs",
    "genomics_db_import",
    # VQSR filtering
    "variant_recalibrator",
    "apply_vqsr",
]
