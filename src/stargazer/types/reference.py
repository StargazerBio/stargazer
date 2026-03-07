"""
Reference genome asset types for Stargazer.
"""

from dataclasses import dataclass
from typing import ClassVar

from stargazer.types.asset import Asset


@dataclass
class Reference(Asset):
    """Reference FASTA file asset."""

    _asset_key: ClassVar[str] = "reference"
    _field_defaults = {"build": ""}

    @property
    def contigs(self) -> list[str]:
        """Read contig names from the companion .fai index.

        Requires fetch() to have been called first so the ReferenceIndex
        companion is downloaded alongside this reference.
        """
        if self.path is None:
            raise ValueError("Reference has no local path — call fetch() first")
        fai_path = self.path.parent / (self.path.name + ".fai")
        if not fai_path.exists():
            raise FileNotFoundError(
                f"Reference index not found at {fai_path}. "
                f"Run samtools_faidx first, then fetch() to download companions."
            )
        contigs = []
        with open(fai_path) as f:
            for line in f:
                name = line.split("\t", 1)[0].strip()
                if name:
                    contigs.append(name)
        return contigs


@dataclass
class ReferenceIndex(Asset):
    """FASTA index (.fai) file asset.

    Carries reference_cid linking back to the Reference it was built from.
    """

    _asset_key: ClassVar[str] = "reference_index"
    _field_defaults = {"build": ""}


@dataclass
class SequenceDict(Asset):
    """Sequence dictionary (.dict) file asset."""

    _asset_key: ClassVar[str] = "sequence_dict"
    _field_defaults = {"build": ""}


@dataclass
class AlignerIndex(Asset):
    """Aligner index file asset (one file per index file for multi-file indices)."""

    _asset_key: ClassVar[str] = "aligner_index"
    _field_defaults = {"build": "", "aligner": ""}
