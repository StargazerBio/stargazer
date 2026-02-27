"""
Reads types for Stargazer.

Defines ComponentFile subclasses for FASTQ read files and the
Reads container that composes them.
"""

from dataclasses import dataclass
from pathlib import Path

from stargazer.utils.component import ComponentFile
from stargazer.utils.storage import default_client


# ---------------------------------------------------------------------------
# Component file types
# ---------------------------------------------------------------------------


@dataclass
class R1File(ComponentFile):
    """R1 (forward) FASTQ read file component."""

    def __post_init__(self):
        self.keyvalues.setdefault("type", "reads")
        self.keyvalues.setdefault("component", "r1")

    @property
    def sample_id(self) -> str:
        return self.keyvalues.get("sample_id", "")

    @sample_id.setter
    def sample_id(self, value: str) -> None:
        self.keyvalues["sample_id"] = value

    @property
    def sequencing_platform(self) -> str | None:
        return self.keyvalues.get("sequencing_platform")

    @sequencing_platform.setter
    def sequencing_platform(self, value: str) -> None:
        self.keyvalues["sequencing_platform"] = value

    async def update(
        self,
        path: Path,
        *,
        sample_id: str | None = None,
        sequencing_platform: str | None = None,
    ) -> None:
        """Upload R1 FASTQ file and set cid."""
        if sample_id is not None:
            self.keyvalues["sample_id"] = sample_id
        if sequencing_platform is not None:
            self.keyvalues["sequencing_platform"] = sequencing_platform
        self.path = path
        await default_client.upload(self)


@dataclass
class R2File(ComponentFile):
    """R2 (reverse) FASTQ read file component."""

    def __post_init__(self):
        self.keyvalues.setdefault("type", "reads")
        self.keyvalues.setdefault("component", "r2")

    @property
    def sample_id(self) -> str:
        return self.keyvalues.get("sample_id", "")

    @sample_id.setter
    def sample_id(self, value: str) -> None:
        self.keyvalues["sample_id"] = value

    @property
    def sequencing_platform(self) -> str | None:
        return self.keyvalues.get("sequencing_platform")

    @sequencing_platform.setter
    def sequencing_platform(self, value: str) -> None:
        self.keyvalues["sequencing_platform"] = value

    async def update(
        self,
        path: Path,
        *,
        sample_id: str | None = None,
        sequencing_platform: str | None = None,
    ) -> None:
        """Upload R2 FASTQ file and set cid."""
        if sample_id is not None:
            self.keyvalues["sample_id"] = sample_id
        if sequencing_platform is not None:
            self.keyvalues["sequencing_platform"] = sequencing_platform
        self.path = path
        await default_client.upload(self)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


@dataclass
class Reads:
    """
    FASTQ reads stored as typed component files.

    Attributes:
        sample_id: Sample identifier
        r1: R1 (forward) FASTQ file
        r2: R2 (reverse) FASTQ file (None for single-end reads)
        read_group: Optional read group metadata (ID, SM, LB, PL, PU)
    """

    sample_id: str
    r1: R1File | None = None
    r2: R2File | None = None
    read_group: dict[str, str] | None = None

    @property
    def is_paired(self) -> bool:
        """Whether this is paired-end reads (has both R1 and R2)."""
        return self.r1 is not None and self.r2 is not None

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        result: dict = {
            "sample_id": self.sample_id,
            "is_paired": self.is_paired,
        }
        if self.r1:
            result["r1"] = self.r1.to_dict()
        if self.r2:
            result["r2"] = self.r2.to_dict()
        if self.read_group:
            result["read_group"] = self.read_group
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Reads":
        """Reconstruct from a serialized dict."""
        reads = cls(sample_id=data["sample_id"])
        if "r1" in data:
            reads.r1 = R1File.from_dict(data["r1"])
        if "r2" in data:
            reads.r2 = R2File.from_dict(data["r2"])
        if "read_group" in data:
            reads.read_group = data["read_group"]
        return reads

    async def fetch(self) -> Path:
        """
        Fetch all reads component files to local cache.

        Downloads all non-None component files. Returns the cache directory.
        """
        components = [c for c in [self.r1, self.r2] if c is not None]

        if not components:
            raise ValueError("No files to fetch. Reads has no components set.")

        for c in components:
            await default_client.download(c)

        return default_client.local_dir
