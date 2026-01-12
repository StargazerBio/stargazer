"""
Stargazer tasks for bioinformatics workflows.
"""

from stargazer.tasks.samtools import samtools_faidx
from stargazer.tasks.bwa import bwa_index
from stargazer.tasks.bwa_mem import bwa_mem
from stargazer.tasks.parabricks.fq2bam import fq2bam
from stargazer.tasks.parabricks.deepvariant import deepvariant
from stargazer.tasks.parabricks.haplotypecaller import haplotypecaller

# GATK tasks
from stargazer.tasks.gatk.baserecalibrator import baserecalibrator
from stargazer.tasks.gatk.applybqsr import applybqsr
from stargazer.tasks.gatk.markduplicates import markduplicates
from stargazer.tasks.gatk.sortsam import sortsam
from stargazer.tasks.gatk.mergebamalignment import mergebamalignment
from stargazer.tasks.gatk.indexgvcf import indexgvcf
from stargazer.tasks.gatk.genotypegvcf import genotypegvcf
from stargazer.tasks.gatk.combinegvcfs import combinegvcfs

__all__ = [
    # Reference indexing
    "samtools_faidx",
    "bwa_index",
    # Alignment
    "bwa_mem",
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
