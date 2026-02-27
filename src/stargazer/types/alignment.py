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

    def __post_init__(self):
        self.keyvalues.setdefault("type", "alignment")
        self.keyvalues.setdefault("component", "alignment")

    @property
    def sample_id(self) -> str:
        return self.keyvalues.get("sample_id", "")

    @sample_id.setter
    def sample_id(self, value: str) -> None:
        self.keyvalues["sample_id"] = value

    @property
    def format(self) -> str | None:
        return self.keyvalues.get("format")

    @format.setter
    def format(self, value: str) -> None:
        self.keyvalues["format"] = value

    @property
    def sorted(self) -> str | None:
        return self.keyvalues.get("sorted")

    @sorted.setter
    def sorted(self, value: str) -> None:
        self.keyvalues["sorted"] = value

    @property
    def duplicates_marked(self) -> bool:
        return self.keyvalues.get("duplicates_marked") == "true"

    @duplicates_marked.setter
    def duplicates_marked(self, value: bool) -> None:
        self.keyvalues["duplicates_marked"] = "true" if value else "false"

    @property
    def bqsr_applied(self) -> bool:
        return self.keyvalues.get("bqsr_applied") == "true"

    @bqsr_applied.setter
    def bqsr_applied(self, value: bool) -> None:
        self.keyvalues["bqsr_applied"] = "true" if value else "false"

    @property
    def tool(self) -> str | None:
        return self.keyvalues.get("tool")

    @tool.setter
    def tool(self, value: str) -> None:
        self.keyvalues["tool"] = value

    async def update(
        self,
        path: Path,
        *,
        sample_id: str | None = None,
        format: str | None = None,
        sorted: str | None = None,
        duplicates_marked: bool | None = None,
        bqsr_applied: bool | None = None,
        tool: str | None = None,
    ) -> None:
        """Upload alignment file and set cid."""
        if sample_id is not None:
            self.keyvalues["sample_id"] = sample_id
        if format is not None:
            self.keyvalues["format"] = format
        if sorted is not None:
            self.keyvalues["sorted"] = sorted
        if duplicates_marked is not None:
            self.keyvalues["duplicates_marked"] = (
                "true" if duplicates_marked else "false"
            )
        if bqsr_applied is not None:
            self.keyvalues["bqsr_applied"] = "true" if bqsr_applied else "false"
        if tool is not None:
            self.keyvalues["tool"] = tool
        self.path = path
        await default_client.upload(self)


@dataclass
class AlignmentIndex(ComponentFile):
    """BAI/CRAI alignment index file component."""

    def __post_init__(self):
        self.keyvalues.setdefault("type", "alignment")
        self.keyvalues.setdefault("component", "index")

    @property
    def sample_id(self) -> str:
        return self.keyvalues.get("sample_id", "")

    @sample_id.setter
    def sample_id(self, value: str) -> None:
        self.keyvalues["sample_id"] = value

    async def update(self, path: Path, *, sample_id: str | None = None) -> None:
        """Upload alignment index file and set cid."""
        if sample_id is not None:
            self.keyvalues["sample_id"] = sample_id
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
