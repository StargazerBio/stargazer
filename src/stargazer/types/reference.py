"""
Reference genome types for Stargazer.

Defines ComponentFile subclasses for reference genome files and the
Reference container that composes them.
"""

from dataclasses import dataclass, field
from pathlib import Path

from stargazer.utils.component import ComponentFile
from stargazer.utils.storage import default_client


# ---------------------------------------------------------------------------
# Component file types
# ---------------------------------------------------------------------------


@dataclass
class ReferenceFile(ComponentFile):
    """Reference FASTA file component."""

    _field_defaults = {"build": ""}

    def __post_init__(self):
        self.keyvalues.setdefault("type", "reference")
        self.keyvalues.setdefault("component", "fasta")

    async def update(self, path: Path, **kwargs) -> None:
        """Upload FASTA file and set cid."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)


@dataclass
class ReferenceIndex(ComponentFile):
    """FASTA index (.fai) file component."""

    _field_defaults = {"build": ""}

    def __post_init__(self):
        self.keyvalues.setdefault("type", "reference")
        self.keyvalues.setdefault("component", "faidx")

    async def update(self, path: Path, **kwargs) -> None:
        """Upload FASTA index file and set cid."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)


@dataclass
class SequenceDict(ComponentFile):
    """Sequence dictionary (.dict) file component."""

    _field_defaults = {"build": ""}

    def __post_init__(self):
        self.keyvalues.setdefault("type", "reference")
        self.keyvalues.setdefault("component", "sequence_dictionary")

    async def update(self, path: Path, **kwargs) -> None:
        """Upload sequence dictionary file and set cid."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)


@dataclass
class AlignerIndex(ComponentFile):
    """Aligner index file component (one file per index file for multi-file indices)."""

    _field_defaults = {"build": "", "aligner": ""}

    def __post_init__(self):
        self.keyvalues.setdefault("type", "reference")
        self.keyvalues.setdefault("component", "aligner_index")

    async def update(self, path: Path, **kwargs) -> None:
        """Upload aligner index file and set cid."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


@dataclass
class Reference:
    """
    A reference genome stored as typed component files.

    Attributes:
        build: Reference genome build (e.g., "GRCh38", "T2T-CHM13")
        fasta: Reference FASTA file
        faidx: FASTA index (.fai) file
        sequence_dictionary: Sequence dictionary (.dict) file
        aligner_index: Aligner index files (one per file in multi-file index)
    """

    build: str
    fasta: ReferenceFile | None = None
    faidx: ReferenceIndex | None = None
    sequence_dictionary: SequenceDict | None = None
    aligner_index: list[AlignerIndex] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        result: dict = {"build": self.build}
        if self.fasta:
            result["fasta"] = self.fasta.to_dict()
        if self.faidx:
            result["faidx"] = self.faidx.to_dict()
        if self.sequence_dictionary:
            result["sequence_dictionary"] = self.sequence_dictionary.to_dict()
        if self.aligner_index:
            result["aligner_index"] = [f.to_dict() for f in self.aligner_index]
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Reference":
        """Reconstruct from a serialized dict."""
        ref = cls(build=data["build"])
        if "fasta" in data:
            ref.fasta = ReferenceFile.from_dict(data["fasta"])
        if "faidx" in data:
            ref.faidx = ReferenceIndex.from_dict(data["faidx"])
        if "sequence_dictionary" in data:
            ref.sequence_dictionary = SequenceDict.from_dict(
                data["sequence_dictionary"]
            )
        if "aligner_index" in data:
            ref.aligner_index = [
                AlignerIndex.from_dict(f) for f in data["aligner_index"]
            ]
        return ref

    async def fetch(self) -> Path:
        """
        Fetch all reference component files to local cache.

        Downloads all non-None component files. Returns the cache directory.
        """
        components: list[ComponentFile] = []
        if self.fasta is not None:
            components.append(self.fasta)
        if self.faidx is not None:
            components.append(self.faidx)
        if self.sequence_dictionary is not None:
            components.append(self.sequence_dictionary)
        components.extend(self.aligner_index)

        if not components:
            raise ValueError("No files to fetch. Reference has no components set.")

        for c in components:
            await default_client.download(c)

        return default_client.local_dir
