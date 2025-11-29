"""
Output dataclasses for NVIDIA Parabricks genomics tools.

This module defines the output structures returned by Parabricks Flyte tasks.
"""

from dataclasses import dataclass
from typing import Optional

from flyte.io import File


@dataclass
class Fq2BamOutputs:
    """Output files from fq2bam tool."""
    bam: File  # Output BAM/CRAM file
    recal_file: Optional[File] = None  # BQSR recalibration report
    duplicate_metrics: Optional[File] = None  # Duplicate metrics file


@dataclass
class DeepVariantOutputs:
    """Output files from DeepVariant tool."""
    variants: File  # Output VCF file with variant calls


@dataclass
class HaplotypeCallerOutputs:
    """Output files from HaplotypeCaller tool."""
    variants: File  # Output VCF file with variant calls
    htvc_bam: Optional[File] = None  # Assembled haplotypes BAM (if requested)
