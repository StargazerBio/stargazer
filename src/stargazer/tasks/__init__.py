"""
Stargazer tasks for bioinformatics workflows.
"""

from stargazer.tasks.general.hydrate import hydrate
from stargazer.tasks.general.samtools import samtools_faidx
from stargazer.tasks.general.bwa import bwa_index, bwa_mem

# GATK tasks
from stargazer.tasks.gatk.baserecalibrator import baserecalibrator
from stargazer.tasks.gatk.applybqsr import applybqsr
from stargazer.tasks.gatk.analyzecovariates import analyzecovariates
from stargazer.tasks.gatk.markduplicates import markduplicates
from stargazer.tasks.gatk.sortsam import sortsam
from stargazer.tasks.gatk.mergebamalignment import mergebamalignment
from stargazer.tasks.gatk.genotypegvcf import genotypegvcf
from stargazer.tasks.gatk.combinegvcfs import combinegvcfs
from stargazer.tasks.gatk.genomicsdbimport import genomicsdbimport
from stargazer.tasks.gatk.variantrecalibrator import variantrecalibrator, VQSRResource
from stargazer.tasks.gatk.applyvqsr import applyvqsr

__all__ = [
    # Hydration
    "hydrate",
    # Reference indexing
    "samtools_faidx",
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
