"""
Variants type for Stargazer.

Represents variant calls in VCF/GVCF format stored in IPFS.
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from stargazer.utils.pinata import default_client, IpFile


@dataclass
class Variants:
    """
    Variant calls in VCF/GVCF format stored as IPFS files.

    Attributes:
        sample_id: Sample identifier
        vcf: VCF/GVCF file
        index: VCF index (.tbi) file

    Properties:
        caller: Variant caller used (read from vcf keyvalues)
        is_gvcf: Whether this is a GVCF (read from vcf keyvalues)
        is_multi_sample: Whether this is a multi-sample VCF (read from vcf keyvalues)
        source_samples: List of source sample IDs for multi-sample VCF
    """

    sample_id: str
    vcf: Optional[IpFile] = None
    index: Optional[IpFile] = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        result: dict = {
            "sample_id": self.sample_id,
            "caller": self.caller,
            "is_gvcf": self.is_gvcf,
            "is_multi_sample": self.is_multi_sample,
            "source_samples": self.source_samples,
        }
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
            v.vcf = IpFile.from_dict(data["vcf"])
        if "index" in data:
            v.index = IpFile.from_dict(data["index"])
        return v

    @property
    def caller(self) -> str:
        """
        Variant caller used to generate this VCF.

        Reads from the vcf file's keyvalues metadata.

        Returns:
            Caller name (e.g., "deepvariant", "haplotypecaller") or "unknown"
        """
        if self.vcf:
            return self.vcf.keyvalues.get("caller", "unknown")
        return "unknown"

    @property
    def is_gvcf(self) -> bool:
        """
        Whether this is a GVCF file.

        Reads from the vcf file's keyvalues metadata.

        Returns:
            True if variant_type="gvcf" in vcf keyvalues, False otherwise
        """
        if self.vcf:
            return self.vcf.keyvalues.get("variant_type") == "gvcf"
        return False

    @property
    def is_multi_sample(self) -> bool:
        """
        Whether this is a multi-sample VCF/GVCF (e.g., from CombineGVCFs).

        Reads from the vcf file's keyvalues metadata.

        Returns:
            True if sample_count > 1 in vcf keyvalues, False otherwise
        """
        if self.vcf:
            sample_count = self.vcf.keyvalues.get("sample_count", "1")
            try:
                return int(sample_count) > 1
            except ValueError:
                return False
        return False

    @property
    def source_samples(self) -> list[str]:
        """
        List of source sample IDs for multi-sample VCF/GVCF.

        For single-sample files, returns a list with just sample_id.
        For multi-sample files (e.g., from CombineGVCFs), returns all
        source sample IDs.

        Returns:
            List of sample IDs that contributed to this variant file
        """
        if self.vcf:
            source = self.vcf.keyvalues.get("source_samples", "")
            if source:
                return source.split(",")
        return [self.sample_id]

    async def update_vcf(
        self,
        path: Path,
        caller: Optional[str] = None,
        variant_type: Optional[str] = None,
        build: Optional[str] = None,
        sample_count: Optional[int] = None,
        source_samples: Optional[list[str]] = None,
    ) -> IpFile:
        """
        Upload VCF/GVCF component.

        Args:
            path: Path to file to upload
            caller: Variant caller used (e.g., "deepvariant", "haplotypecaller")
            variant_type: "vcf" or "gvcf"
            build: Reference build (e.g., "GRCh38")
            sample_count: Number of samples in the VCF
            source_samples: List of source sample IDs for multi-sample VCF

        Returns:
            IpFile representing the uploaded file
        """
        keyvalues = {
            "type": "variants",
            "component": "vcf",
            "sample_id": self.sample_id,
        }

        if caller:
            keyvalues["caller"] = caller
        if variant_type:
            keyvalues["variant_type"] = variant_type
        if build:
            keyvalues["build"] = build
        if sample_count is not None:
            keyvalues["sample_count"] = str(sample_count)
        if source_samples:
            keyvalues["source_samples"] = ",".join(source_samples)

        ipfile = await default_client.upload_file(path, keyvalues=keyvalues)
        self.vcf = ipfile
        return self.vcf

    async def update_index(
        self,
        path: Path,
    ) -> IpFile:
        """
        Upload VCF index (.tbi) component.

        Args:
            path: Path to file to upload

        Returns:
            IpFile representing the uploaded file
        """
        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "variants",
                "component": "index",
                "sample_id": self.sample_id,
            },
        )
        self.index = ipfile
        return self.index

    async def fetch(self) -> Path:
        """
        Fetch all variant component files to local cache.

        Downloads all non-None component files to the PinataClient cache.
        Returns the cache directory containing all files.

        Returns:
            Path to cache directory containing all variant files
        """
        components = [self.vcf, self.index]
        files_to_fetch = [f for f in components if f is not None]

        if not files_to_fetch:
            raise ValueError("No files to fetch. Variants has no components set.")

        for ipfile in files_to_fetch:
            await default_client.download_file(ipfile)

        return default_client.local_dir
