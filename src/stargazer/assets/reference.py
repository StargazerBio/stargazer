"""
### Reference genome asset types for Stargazer.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

from dataclasses import dataclass
from typing import ClassVar

import aiofiles

from stargazer.assets.asset import Asset


@dataclass
class Reference(Asset):
    """Reference FASTA file asset."""

    _asset_key: ClassVar[str] = "reference"
    build: str = ""

    async def contigs(self) -> list[str]:
        """Read contig names from the companion .fai index.

        Fetches the reference first, which brings the ReferenceIndex
        companion alongside the local copy, so it works in any pod.
        """
        path = await self.fetch()
        fai_path = path.with_name(path.name + ".fai")
        if not fai_path.exists():
            raise FileNotFoundError(
                f"Reference index not found at {fai_path}. Run samtools_faidx first."
            )
        async with aiofiles.open(fai_path) as f:
            lines = (await f.read()).splitlines()
        return [line.split("\t", 1)[0].strip() for line in lines if line.strip()]


@dataclass
class ReferenceIndex(Asset):
    """FASTA index (.fai) file asset.

    Carries reference_cid linking back to the Reference it was built from.
    """

    _asset_key: ClassVar[str] = "reference_index"
    build: str = ""
    tool: str = ""
    reference_cid: str = ""


@dataclass
class SequenceDict(Asset):
    """Sequence dictionary (.dict) file asset."""

    _asset_key: ClassVar[str] = "sequence_dict"
    build: str = ""
    tool: str = ""
    reference_cid: str = ""


@dataclass
class AlignerIndex(Asset):
    """Aligner index file asset (one file per index file for multi-file indices)."""

    _asset_key: ClassVar[str] = "aligner_index"
    build: str = ""
    aligner: str = ""
    reference_cid: str = ""
