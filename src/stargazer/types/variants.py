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

    def __post_init__(self):
        self.keyvalues.setdefault("type", "variants")
        self.keyvalues.setdefault("component", "vcf")

    @property
    def sample_id(self) -> str:
        return self.keyvalues.get("sample_id", "")

    @sample_id.setter
    def sample_id(self, value: str) -> None:
        self.keyvalues["sample_id"] = value

    @property
    def caller(self) -> str | None:
        return self.keyvalues.get("caller")

    @caller.setter
    def caller(self, value: str) -> None:
        self.keyvalues["caller"] = value

    @property
    def variant_type(self) -> str | None:
        return self.keyvalues.get("variant_type")

    @variant_type.setter
    def variant_type(self, value: str) -> None:
        self.keyvalues["variant_type"] = value

    @property
    def build(self) -> str | None:
        return self.keyvalues.get("build")

    @build.setter
    def build(self, value: str) -> None:
        self.keyvalues["build"] = value

    @property
    def sample_count(self) -> int | None:
        val = self.keyvalues.get("sample_count")
        return int(val) if val is not None else None

    @sample_count.setter
    def sample_count(self, value: int) -> None:
        self.keyvalues["sample_count"] = str(value)

    @property
    def source_samples(self) -> list[str] | None:
        val = self.keyvalues.get("source_samples")
        return val.split(",") if val else None

    @source_samples.setter
    def source_samples(self, value: list[str]) -> None:
        self.keyvalues["source_samples"] = ",".join(value)

    async def update(
        self,
        path: Path,
        *,
        sample_id: str | None = None,
        caller: str | None = None,
        variant_type: str | None = None,
        build: str | None = None,
        sample_count: int | None = None,
        source_samples: list[str] | None = None,
    ) -> None:
        """Upload VCF/GVCF file and set cid."""
        if sample_id is not None:
            self.keyvalues["sample_id"] = sample_id
        if caller is not None:
            self.keyvalues["caller"] = caller
        if variant_type is not None:
            self.keyvalues["variant_type"] = variant_type
        if build is not None:
            self.keyvalues["build"] = build
        if sample_count is not None:
            self.keyvalues["sample_count"] = str(sample_count)
        if source_samples is not None:
            self.keyvalues["source_samples"] = ",".join(source_samples)
        self.path = path
        await default_client.upload(self)


@dataclass
class VariantsIndex(ComponentFile):
    """VCF index (.tbi) file component."""

    def __post_init__(self):
        self.keyvalues.setdefault("type", "variants")
        self.keyvalues.setdefault("component", "index")

    @property
    def sample_id(self) -> str:
        return self.keyvalues.get("sample_id", "")

    @sample_id.setter
    def sample_id(self, value: str) -> None:
        self.keyvalues["sample_id"] = value

    async def update(self, path: Path, *, sample_id: str | None = None) -> None:
        """Upload VCF index file and set cid."""
        if sample_id is not None:
            self.keyvalues["sample_id"] = sample_id
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
