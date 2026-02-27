"""
Alignment types for Stargazer.

Defines ComponentFile subclasses for BAM/CRAM alignment files and the
Alignment container that composes them.
"""

from dataclasses import dataclass
from pathlib import Path

from stargazer.utils.component import ComponentFile
from stargazer.utils.storage import default_client


# ---------------------------------------------------------------------------
# Component file types
# ---------------------------------------------------------------------------


@dataclass
class AlignmentFile(ComponentFile):
    """BAM/CRAM alignment file component."""

    _field_types = {"duplicates_marked": bool, "bqsr_applied": bool}
    _field_defaults = {"sample_id": ""}

    def __post_init__(self):
        self.keyvalues.setdefault("type", "alignment")
        self.keyvalues.setdefault("component", "alignment")

    async def update(self, path: Path, **kwargs) -> None:
        """Upload alignment file and set cid."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)


@dataclass
class AlignmentIndex(ComponentFile):
    """BAI/CRAI alignment index file component."""

    _field_defaults = {"sample_id": ""}

    def __post_init__(self):
        self.keyvalues.setdefault("type", "alignment")
        self.keyvalues.setdefault("component", "index")

    async def update(self, path: Path, **kwargs) -> None:
        """Upload alignment index file and set cid."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


@dataclass
class Alignment:
    """
    Aligned BAM/CRAM files stored as typed component files.

    Attributes:
        sample_id: Sample identifier
        alignment: BAM/CRAM alignment file
        index: BAI/CRAI index file
    """

    sample_id: str
    alignment: AlignmentFile | None = None
    index: AlignmentIndex | None = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        result: dict = {"sample_id": self.sample_id}
        if self.alignment:
            result["alignment"] = self.alignment.to_dict()
        if self.index:
            result["index"] = self.index.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Alignment":
        """Reconstruct from a serialized dict."""
        aln = cls(sample_id=data["sample_id"])
        if "alignment" in data:
            aln.alignment = AlignmentFile.from_dict(data["alignment"])
        if "index" in data:
            aln.index = AlignmentIndex.from_dict(data["index"])
        return aln

    async def fetch(self) -> Path:
        """
        Fetch all alignment component files to local cache.

        Downloads all non-None component files. Returns the cache directory.
        """
        components = [c for c in [self.alignment, self.index] if c is not None]

        if not components:
            raise ValueError("No files to fetch. Alignment has no components set.")

        for c in components:
            await default_client.download(c)

        return default_client.local_dir
