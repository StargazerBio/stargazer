"""
Stargazer tasks for bioinformatics workflows.
"""

from stargazer.tasks.samtools import samtools_faidx
from stargazer.tasks.bwa import bwa_index
from stargazer.tasks.fq2bam import fq2bam
from stargazer.tasks.deepvariant import deepvariant
from stargazer.tasks.haplotypecaller import haplotypecaller
from stargazer.tasks.indexgvcf import indexgvcf
from stargazer.tasks.genotypegvcf import genotypegvcf
from stargazer.tasks.combinegvcfs import combinegvcfs

# GATK tasks
from stargazer.tasks.gatk.baserecalibrator import baserecalibrator
from stargazer.tasks.gatk.applybqsr import applybqsr
from stargazer.tasks.gatk.markduplicates import markduplicates
from stargazer.tasks.gatk.sortsam import sortsam
from stargazer.tasks.gatk.mergebamalignment import mergebamalignment

__all__ = [
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
    # Variant calling
    "deepvariant",
    "haplotypecaller",
    # GVCF processing
    "indexgvcf",
    "genotypegvcf",
    "combinegvcfs",
]
