"""
Stargazer tasks for bioinformatics workflows.
"""

from stargazer.tasks.general.hydrate import hydrate
from stargazer.tasks.general.samtools import samtools_faidx
from stargazer.tasks.general.bwa import bwa_index, bwa_mem
from stargazer.tasks.gatk.create_sequence_dictionary import create_sequence_dictionary

# GATK tasks
from stargazer.tasks.gatk.base_recalibrator import baserecalibrator
from stargazer.tasks.gatk.apply_bqsr import applybqsr
from stargazer.tasks.gatk.analyze_covariates import analyzecovariates
from stargazer.tasks.gatk.mark_duplicates import markduplicates
from stargazer.tasks.gatk.sort_sam import sortsam
from stargazer.tasks.gatk.merge_bam_alignment import mergebamalignment
from stargazer.tasks.gatk.genotype_gvcf import genotypegvcf
from stargazer.tasks.gatk.combine_gvcfs import combinegvcfs
from stargazer.tasks.gatk.genomics_db_import import genomicsdbimport
from stargazer.tasks.gatk.variant_recalibrator import variantrecalibrator, VQSRResource
from stargazer.tasks.gatk.apply_vqsr import applyvqsr

__all__ = [
    # Hydration
    "hydrate",
    # Reference indexing
    "samtools_faidx",
    "create_sequence_dictionary",
    "bwa_index",
    "bwa_mem",
    # Data preprocessing (GATK)
    "sortsam",
    "markduplicates",
    "mergebamalignment",
    # BQSR (Base Quality Score Recalibration)
    "baserecalibrator",
    "applybqsr",
    "analyzecovariates",
    # GVCF processing
    "genotypegvcf",
    "combinegvcfs",
    "genomicsdbimport",
    # Variant filtering (VQSR)
    "variantrecalibrator",
    "VQSRResource",
    "applyvqsr",
]
