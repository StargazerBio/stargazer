"""
Reference genome type for Stargazer.

A reference is a collection of component files (FASTA, indices) stored in IPFS.
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from stargazer.utils.storage import default_client
from stargazer.utils.ipfile import IpFile


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
    sequence_dictionary: Optional[IpFile] = None
    aligner_index: list[IpFile] = field(default_factory=list)

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
            ref.fasta = IpFile.from_dict(data["fasta"])
        if "faidx" in data:
            ref.faidx = IpFile.from_dict(data["faidx"])
        if "sequence_dictionary" in data:
            ref.sequence_dictionary = IpFile.from_dict(data["sequence_dictionary"])
        if "aligner_index" in data:
            ref.aligner_index = [IpFile.from_dict(f) for f in data["aligner_index"]]
        return ref

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
        tool: Optional[str] = None,
    ) -> IpFile:
        """
        Upload FASTA index (.fai) component.

        Args:
            path: Path to file to upload
            build: Reference build (uses self.build if not provided)
            tool: Tool that created the index (e.g., "samtools_faidx")

        Returns:
            IpFile representing the uploaded file
        """
        keyvalues = {
            "type": "reference",
            "component": "faidx",
            "build": build or self.build,
        }
        if tool:
            keyvalues["tool"] = tool

        ipfile = await default_client.upload_file(path, keyvalues=keyvalues)
        self.faidx = ipfile
        return self.faidx

    async def update_sequence_dictionary(
        self,
        path: Path,
        build: Optional[str] = None,
        tool: Optional[str] = None,
    ) -> IpFile:
        """
        Upload sequence dictionary (.dict) component.

        Args:
            path: Path to file to upload
            build: Reference build (uses self.build if not provided)
            tool: Tool that created the dictionary (e.g., "gatk_CreateSequenceDictionary")

        Returns:
            IpFile representing the uploaded file
        """
        keyvalues = {
            "type": "reference",
            "component": "sequence_dictionary",
            "build": build or self.build,
        }
        if tool:
            keyvalues["tool"] = tool

        ipfile = await default_client.upload_file(path, keyvalues=keyvalues)
        self.sequence_dictionary = ipfile
        return self.sequence_dictionary

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
        if self.sequence_dictionary is not None:
            files_to_fetch.append(self.sequence_dictionary)
        files_to_fetch.extend(self.aligner_index)

        if not files_to_fetch:
            raise ValueError("No files to fetch. Reference has no components set.")

        for ipfile in files_to_fetch:
            await default_client.download_file(ipfile)

        return default_client.local_dir
