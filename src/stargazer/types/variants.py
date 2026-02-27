"""
Variants types for Stargazer.

Defines ComponentFile subclasses for VCF/GVCF variant call files and the
Variants container that composes them.
"""

from dataclasses import dataclass
from pathlib import Path

from stargazer.utils.component import ComponentFile
from stargazer.utils.storage import default_client


# ---------------------------------------------------------------------------
# Component file types
# ---------------------------------------------------------------------------


@dataclass
class VariantsFile(ComponentFile):
    """VCF/GVCF variant call file component."""

    _field_types = {"sample_count": int, "source_samples": list}
    _field_defaults = {"sample_id": ""}

    def __post_init__(self):
        self.keyvalues.setdefault("type", "variants")
        self.keyvalues.setdefault("component", "vcf")

    async def update(self, path: Path, **kwargs) -> None:
        """Upload VCF/GVCF file and set cid."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)


@dataclass
class VariantsIndex(ComponentFile):
    """VCF index (.tbi) file component."""

    _field_defaults = {"sample_id": ""}

    def __post_init__(self):
        self.keyvalues.setdefault("type", "variants")
        self.keyvalues.setdefault("component", "index")

    async def update(self, path: Path, **kwargs) -> None:
        """Upload VCF index file and set cid."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(self, key, value)
        self.path = path
        await default_client.upload(self)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


@dataclass
class Variants:
    """
    Variant calls in VCF/GVCF format stored as typed component files.

    Attributes:
        sample_id: Sample identifier
        vcf: VCF/GVCF file
        index: VCF index (.tbi) file
    """

    sample_id: str
    vcf: VariantsFile | None = None
    index: VariantsIndex | None = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        result: dict = {"sample_id": self.sample_id}
        if self.vcf:
            result["vcf"] = self.vcf.to_dict()
        if self.index:
            result["index"] = self.index.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Variants":
        """Reconstruct from a serialized dict."""
        v = cls(sample_id=data["sample_id"])
        if "vcf" in data:
            v.vcf = VariantsFile.from_dict(data["vcf"])
        if "index" in data:
            v.index = VariantsIndex.from_dict(data["index"])
        return v

    async def fetch(self) -> Path:
        """
        Fetch all variant component files to local cache.

        Downloads all non-None component files. Returns the cache directory.
        """
        components = [c for c in [self.vcf, self.index] if c is not None]

        if not components:
            raise ValueError("No files to fetch. Variants has no components set.")

        for c in components:
            await default_client.download(c)

        return default_client.local_dir
