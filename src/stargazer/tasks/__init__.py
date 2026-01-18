"""
Stargazer tasks for bioinformatics workflows.
"""

from stargazer.tasks.hydrate import hydrate
from stargazer.tasks.samtools import samtools_faidx
from stargazer.tasks.bwa import bwa_index
from stargazer.tasks.parabricks.fq2bam import fq2bam
from stargazer.tasks.parabricks.deepvariant import deepvariant
from stargazer.tasks.parabricks.haplotypecaller import haplotypecaller

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
    # Alignment
    "fq2bam",
    # Data preprocessing (GATK)
    "sortsam",
    "markduplicates",
    "mergebamalignment",
    # BQSR (Base Quality Score Recalibration)
    "baserecalibrator",
    "applybqsr",
    "analyzecovariates",
    # Variant calling
    "deepvariant",
    "haplotypecaller",
    # GVCF processing
    "genotypegvcf",
    "combinegvcfs",
    "genomicsdbimport",
    # Variant filtering (VQSR)
    "variantrecalibrator",
    "VQSRResource",
    "applyvqsr",
]
