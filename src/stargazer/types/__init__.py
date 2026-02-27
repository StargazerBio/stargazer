"""
Stargazer types for bioinformatics workflows.
"""

from stargazer.utils.component import ComponentFile
from stargazer.types.reference import (
    Reference,
    ReferenceFile,
    ReferenceIndex,
    SequenceDict,
    AlignerIndex,
)
from stargazer.types.reads import Reads, R1File, R2File
from stargazer.types.alignment import Alignment, AlignmentFile, AlignmentIndex
from stargazer.types.variants import Variants, VariantsFile, VariantsIndex

__all__ = [
    # Base
    "ComponentFile",
    # Reference
    "Reference",
    "ReferenceFile",
    "ReferenceIndex",
    "SequenceDict",
    "AlignerIndex",
    # Reads
    "Reads",
    "R1File",
    "R2File",
    # Alignment
    "Alignment",
    "AlignmentFile",
    "AlignmentIndex",
    # Variants
    "Variants",
    "VariantsFile",
    "VariantsIndex",
]
