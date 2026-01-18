"""
Reads type for Stargazer.

Represents paired-end or single-end FASTQ files stored in IPFS.
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from stargazer.utils.pinata import default_client, IpFile


@dataclass
class Reads:
    """
    FASTQ reads stored as IPFS files.

    Attributes:
        sample_id: Sample identifier
        r1: R1 (forward) FASTQ file
        r2: R2 (reverse) FASTQ file (None for single-end reads)
        read_group: Optional read group metadata (ID, SM, LB, PL, PU)
    """

    sample_id: str
    r1: Optional[IpFile] = None
    r2: Optional[IpFile] = None
    read_group: dict[str, str] | None = None

    @property
    def is_paired(self) -> bool:
        """Whether this is paired-end reads (has both R1 and R2)."""
        return self.r1 is not None and self.r2 is not None

    async def update_r1(
        self,
        path: Path,
        read_type: Optional[str] = None,
        sequencing_platform: Optional[str] = None,
    ) -> IpFile:
        """
        Upload R1 (forward) FASTQ component.

        Args:
            path: Path to file to upload
            sequencing_platform: Sequencing platform (e.g., "ILLUMINA")

        Returns:
            IpFile representing the uploaded file
        """
        keyvalues = {
            "type": "reads",
            "component": "r1",
            "sample_id": self.sample_id,
        }

        if sequencing_platform:
            keyvalues["sequencing_platform"] = sequencing_platform

        ipfile = await default_client.upload_file(path, keyvalues=keyvalues)
        self.r1 = ipfile
        return self.r1

    async def update_r2(
        self,
        path: Path,
        sequencing_platform: Optional[str] = None,
    ) -> IpFile:
        """
        Upload R2 (reverse) FASTQ component.

        Args:
            path: Path to file to upload
            sequencing_platform: Sequencing platform (e.g., "ILLUMINA")

        Returns:
            IpFile representing the uploaded file
        """
        keyvalues = {
            "type": "reads",
            "component": "r2",
            "sample_id": self.sample_id,
        }

        if sequencing_platform:
            keyvalues["sequencing_platform"] = sequencing_platform

        ipfile = await default_client.upload_file(path, keyvalues=keyvalues)
        self.r2 = ipfile
        return self.r2

    async def fetch(self) -> Path:
        """
        Fetch all reads component files to local cache.

        Downloads all non-None component files to the PinataClient cache.
        Returns the cache directory containing all files.

        Returns:
            Path to cache directory containing all FASTQ files
        """
        components = [self.r1, self.r2]
        files_to_fetch = [f for f in components if f is not None]

        if not files_to_fetch:
            raise ValueError("No files to fetch. Reads has no components set.")

        for ipfile in files_to_fetch:
            await default_client.download_file(ipfile)

        return default_client.cache_dir
