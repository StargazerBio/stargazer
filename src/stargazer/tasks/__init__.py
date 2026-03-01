"""
Stargazer tasks for bioinformatics workflows.
"""

from stargazer.tasks.general.hydrate import hydrate
from stargazer.tasks.general.samtools import samtools_faidx
from stargazer.tasks.general.bwa import bwa_index, bwa_mem
from stargazer.tasks.gatk.create_sequence_dictionary import create_sequence_dictionary

# GATK tasks
from stargazer.tasks.gatk.base_recalibrator import base_recalibrator
from stargazer.tasks.gatk.apply_bqsr import apply_bqsr
from stargazer.tasks.gatk.mark_duplicates import mark_duplicates
from stargazer.tasks.gatk.sort_sam import sort_sam
from stargazer.tasks.gatk.merge_bam_alignment import merge_bam_alignment
from stargazer.tasks.gatk.genotype_gvcf import genotype_gvcf
from stargazer.tasks.gatk.combine_gvcfs import combine_gvcfs
from stargazer.tasks.gatk.genomics_db_import import genomics_db_import
from stargazer.tasks.gatk.variant_recalibrator import variant_recalibrator
from stargazer.tasks.gatk.apply_vqsr import apply_vqsr

__all__ = [
    # Hydration
    "hydrate",
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
    "genotype_gvcf",
    "combine_gvcfs",
    "genomics_db_import",
    # Variant filtering (VQSR)
    "variant_recalibrator",
    "apply_vqsr",
]
