"""
Alignment type for Stargazer.

Represents aligned BAM/CRAM files stored in IPFS.
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from stargazer.utils.storage import default_client
from stargazer.utils.ipfile import IpFile


@dataclass
class Alignment:
    """
    Aligned BAM/CRAM files stored as IPFS files.

    Attributes:
        sample_id: Sample identifier
        alignment: BAM/CRAM alignment file
        index: BAI/CRAI index file

    Properties:
        has_duplicates_marked: Whether duplicates are marked (read from alignment keyvalues)
        is_sorted: Whether reads are coordinate sorted (read from alignment keyvalues)
        has_bqsr_applied: Whether BQSR has been applied (read from alignment keyvalues)
    """

    sample_id: str
    alignment: Optional[IpFile] = None
    index: Optional[IpFile] = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        result: dict = {
            "sample_id": self.sample_id,
            "is_sorted": self.is_sorted,
            "has_duplicates_marked": self.has_duplicates_marked,
            "has_bqsr_applied": self.has_bqsr_applied,
        }
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
            aln.alignment = IpFile.from_dict(data["alignment"])
        if "index" in data:
            aln.index = IpFile.from_dict(data["index"])
        return aln

    @property
    def has_duplicates_marked(self) -> bool:
        """
        Whether duplicates are marked in the BAM file.

        Reads from the alignment file's keyvalues metadata.

        Returns:
            True if duplicates_marked="true" in alignment keyvalues, False otherwise
        """
        if self.alignment:
            return self.alignment.keyvalues.get("duplicates_marked") == "true"
        return False

    @property
    def is_sorted(self) -> bool:
        """
        Whether the BAM file is coordinate sorted.

        Reads from the alignment file's keyvalues metadata.

        Returns:
            True if sorted="coordinate" in alignment keyvalues, False otherwise
        """
        if self.alignment:
            return self.alignment.keyvalues.get("sorted") == "coordinate"
        return False

    @property
    def has_bqsr_applied(self) -> bool:
        """
        Whether Base Quality Score Recalibration has been applied.

        Reads from the alignment file's keyvalues metadata.

        Returns:
            True if bqsr_applied="true" in alignment keyvalues, False otherwise
        """
        if self.alignment:
            return self.alignment.keyvalues.get("bqsr_applied") == "true"
        return False

    async def update_alignment(
        self,
        path: Path,
        format: Optional[str] = None,
        is_sorted: Optional[bool] = None,
        duplicates_marked: Optional[bool] = None,
        bqsr_applied: Optional[bool] = None,
        tool: Optional[str] = None,
    ) -> IpFile:
        """
        Upload alignment (BAM/CRAM) component.

        Args:
            path: Path to file to upload
            format: File format ("bam" or "cram")
            is_sorted: Whether alignment is coordinate sorted
            duplicates_marked: Whether duplicates have been marked
            bqsr_applied: Whether BQSR has been applied
            tool: Tool that created the alignment (e.g., "gatk_sort_sam")

        Returns:
            IpFile representing the uploaded file
        """
        keyvalues = {
            "type": "alignment",
            "component": "alignment",
            "sample_id": self.sample_id,
        }

        if format:
            keyvalues["format"] = format
        if is_sorted is not None:
            keyvalues["sorted"] = "coordinate" if is_sorted else "unsorted"
        if duplicates_marked is not None:
            keyvalues["duplicates_marked"] = "true" if duplicates_marked else "false"
        if bqsr_applied is not None:
            keyvalues["bqsr_applied"] = "true" if bqsr_applied else "false"
        if tool:
            keyvalues["tool"] = tool

        ipfile = await default_client.upload_file(path, keyvalues=keyvalues)
        self.alignment = ipfile
        return self.alignment

    async def update_index(
        self,
        path: Path,
    ) -> IpFile:
        """
        Upload alignment index (BAI/CRAI) component.

        Args:
            path: Path to file to upload

        Returns:
            IpFile representing the uploaded file
        """
        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "alignment",
                "component": "index",
                "sample_id": self.sample_id,
            },
        )
        self.index = ipfile
        return self.index

    async def fetch(self) -> Path:
        """
        Fetch all alignment component files to local cache.

        Downloads all non-None component files to the PinataClient cache.
        Returns the cache directory containing all files.

        Returns:
            Path to cache directory containing all alignment files
        """
        components = [self.alignment, self.index]
        files_to_fetch = [f for f in components if f is not None]

        if not files_to_fetch:
            raise ValueError("No files to fetch. Alignment has no components set.")

        for ipfile in files_to_fetch:
            await default_client.download_file(ipfile)

        return default_client.local_dir
