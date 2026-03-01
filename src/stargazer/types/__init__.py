"""
Stargazer types for bioinformatics workflows.
"""

from stargazer.types.component import ComponentFile
from stargazer.types.biotype import BioType
from stargazer.types.reference import (
    Reference,
    ReferenceFile,
    ReferenceIndex,
    SequenceDict,
    AlignerIndex,
)
from stargazer.types.reads import Reads, R1File, R2File
from stargazer.types.alignment import Alignment, AlignmentFile, AlignmentIndex
from stargazer.types.variants import Variants, VariantsFile, VariantsIndex, KnownSites

# Auto-populated via ComponentFile.__init_subclass__
COMPONENT_REGISTRY = ComponentFile._registry


def specialize(component: ComponentFile) -> ComponentFile:
    """Convert a base ComponentFile to its derived type based on keyvalues.

    Looks up the (type, component) pair in the registry and constructs the
    appropriate subclass, preserving cid, path, and all keyvalues. Returns
    the original instance unchanged if no matching derived type is found.
    """
    key = (
        component.keyvalues.get("type", ""),
        component.keyvalues.get("component", ""),
    )
    cls = COMPONENT_REGISTRY.get(key)
    if cls is None:
        return component
    return cls(
        cid=component.cid,
        path=component.path,
        keyvalues=dict(component.keyvalues),
    )


__all__ = [
    # Base
    "ComponentFile",
    "BioType",
    # Derived
    "COMPONENT_REGISTRY",
    "specialize",
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
    "KnownSites",
]
