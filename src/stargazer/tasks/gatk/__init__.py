"""GATK tasks for genomics workflows."""

from stargazer.tasks.gatk.applybqsr import applybqsr
from stargazer.tasks.gatk.baserecalibrator import baserecalibrator
from stargazer.tasks.gatk.markduplicates import markduplicates
from stargazer.tasks.gatk.mergebamalignment import mergebamalignment
from stargazer.tasks.gatk.sortsam import sortsam

__all__ = [
    "applybqsr",
    "baserecalibrator",
    "markduplicates",
    "mergebamalignment",
    "sortsam",
]
