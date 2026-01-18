"""
Reference genome type for Stargazer.

A reference is a collection of component files (FASTA, indices) stored in IPFS.
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from stargazer.utils.pinata import default_client, IpFile


@dataclass
class Reference:
    """
    A reference genome stored as IPFS files.

    Attributes:
        build: Reference genome build (e.g., "GRCh38", "T2T-CHM13")
        fasta: Reference FASTA file
        faidx: FASTA index (.fai) file
        aligner_index: Aligner index files (BWA has .amb, .ann, .bwt, .pac, .sa)
    """

    build: str
    fasta: Optional[IpFile] = None
    faidx: Optional[IpFile] = None
    aligner_index: list[IpFile] = field(default_factory=list)

    async def update_fasta(
        self,
        path: Path,
        build: Optional[str] = None,
    ) -> IpFile:
        """
        Upload reference FASTA component.

        Args:
            path: Path to file to upload
            build: Reference build (uses self.build if not provided)

        Returns:
            IpFile representing the uploaded file
        """
        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "reference",
                "component": "fasta",
                "build": build or self.build,
            },
        )
        self.fasta = ipfile
        return self.fasta

    async def update_faidx(
        self,
        path: Path,
        build: Optional[str] = None,
    ) -> IpFile:
        """
        Upload FASTA index (.fai) component.

        Args:
            path: Path to file to upload
            build: Reference build (uses self.build if not provided)

        Returns:
            IpFile representing the uploaded file
        """
        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "reference",
                "component": "faidx",
                "build": build or self.build,
            },
        )
        self.faidx = ipfile
        return self.faidx

    async def update_aligner_index(
        self,
        path: Path,
        aligner: str,
        build: Optional[str] = None,
    ) -> IpFile:
        """
        Upload aligner index component file.

        Call this method for each file in a multi-file index (e.g., BWA has
        .amb, .ann, .bwt, .pac, .sa files).

        Args:
            path: Path to index file to upload
            aligner: Aligner name (e.g., "bwa", "minimap2")
            build: Reference build (uses self.build if not provided)

        Returns:
            IpFile representing the uploaded index file
        """
        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "reference",
                "component": "aligner_index",
                "aligner": aligner,
                "build": build or self.build,
            },
        )
        self.aligner_index.append(ipfile)
        return ipfile

    async def fetch(self) -> Path:
        """
        Fetch all reference component files to local cache.

        Downloads all non-None component files to the PinataClient cache.
        Returns the cache directory containing all files.

        Returns:
            Path to cache directory containing all reference files
        """
        files_to_fetch: list[IpFile] = []

        if self.fasta is not None:
            files_to_fetch.append(self.fasta)
        if self.faidx is not None:
            files_to_fetch.append(self.faidx)
        files_to_fetch.extend(self.aligner_index)

        if not files_to_fetch:
            raise ValueError("No files to fetch. Reference has no components set.")

        for ipfile in files_to_fetch:
            await default_client.download_file(ipfile)

        return default_client.cache_dir
