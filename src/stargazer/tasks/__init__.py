"""
Stargazer tasks for bioinformatics workflows.
"""

from stargazer.tasks.samtools import samtools_faidx
from stargazer.tasks.bwa import bwa_index
from stargazer.tasks.fq2bam import fq2bam

__all__ = [
    "samtools_faidx",
    "bwa_index",
    "fq2bam",
]
