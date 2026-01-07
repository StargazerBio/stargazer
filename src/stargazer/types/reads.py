"""
Reads type for Stargazer.

Represents paired-end or single-end FASTQ files stored in IPFS.
"""

from dataclasses import dataclass, field
from typing import Self
from pathlib import Path

from stargazer.utils.pinata import default_client, IpFile
from stargazer.utils.query import generate_query_combinations


@dataclass
class Reads:
    """
    FASTQ reads stored as IPFS files.

    Attributes:
        sample_id: Sample identifier
        files: List of IpFile objects containing FASTQ data (R1, R2 for paired-end)
        read_group: Optional read group metadata (ID, SM, LB, PL, PU)
    """

    sample_id: str
    files: list[IpFile] = field(default_factory=list)
    read_group: dict[str, str] | None = None

    async def add_files(
        self,
        file_paths: list[Path],
        keyvalues: dict[str, str] | None = None,
    ) -> None:
        """
        Upload FASTQ files and add to reads.

        Uploads files to IPFS (or copies to local cache if STARGAZER_LOCAL_ONLY is set)
        and adds the resulting IpFile objects to this reads' files list.

        Args:
            file_paths: List of local FASTQ file paths to upload
            keyvalues: Optional metadata key-value pairs to attach to all files

        Raises:
            FileNotFoundError: If any file path doesn't exist
            ValueError: If file_paths is empty

        Example:
            reads = Reads(sample_id="NA12829")
            await reads.add_files(
                file_paths=[Path("R1.fq.gz"), Path("R2.fq.gz")],
                keyvalues={
                    "type": "reads",
                    "sample_id": "NA12829",
                    "read_type": "paired",
                    "sequencing_platform": "ILLUMINA"
                }
            )
        """
        if not file_paths:
            raise ValueError("No files to add. file_paths is empty.")

        # Validate all paths exist before uploading
        for path in file_paths:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")

        # Upload each file (client handles local_only mode) and collect IpFile objects
        for path in file_paths:
            ipfile = await default_client.upload_file(path, keyvalues=keyvalues)
            self.files.append(ipfile)

    async def fetch(self) -> Path:
        """
        Fetch all FASTQ files to local cache.

        Downloads all files in the reads to the PinataClient cache.
        Returns the cache directory containing all files.

        Returns:
            Path to cache directory containing all FASTQ files

        Raises:
            ValueError: If no files to fetch (reads is empty)

        Example:
            reads = await Reads.pinata_hydrate(sample_id="NA12829")
            cache_dir = await reads.fetch()
            # All FASTQ files now in cache_dir
        """
        if not self.files:
            raise ValueError("No files to fetch. Reads is empty.")

        # Download all files to cache and update their paths
        for ipfile in self.files:
            await default_client.download_file(ipfile)

        # Return the cache directory
        return default_client.cache_dir

    def get_r1_path(self) -> Path:
        """
        Get the local cached path to the R1 FASTQ file.

        The reads must be fetched first using fetch().

        Returns:
            Absolute path to the cached R1 FASTQ file

        Raises:
            FileNotFoundError: If R1 file not found or not in cache
        """
        # Find R1 file by name pattern (contains "R1" or "_1")
        r1_file = None
        for f in self.files:
            if f.name and ("R1" in f.name or "_1." in f.name):
                r1_file = f
                break

        if not r1_file:
            raise FileNotFoundError(
                f"R1 file not found in files list for sample {self.sample_id}"
            )

        # Return the path from the IpFile (set by download_file)
        if r1_file.local_path and r1_file.local_path.exists():
            return r1_file.local_path

        raise FileNotFoundError(
            f"R1 file for sample {self.sample_id} not in cache. "
            "Call await reads.fetch() first to download files."
        )

    def get_r2_path(self) -> Path | None:
        """
        Get the local cached path to the R2 FASTQ file.

        For paired-end reads. Returns None for single-end reads.

        Returns:
            Absolute path to the cached R2 FASTQ file, or None for single-end

        Raises:
            FileNotFoundError: If R2 file exists but not in cache
        """
        # Find R2 file by name pattern (contains "R2" or "_2")
        r2_file = None
        for f in self.files:
            if f.name and ("R2" in f.name or "_2." in f.name):
                r2_file = f
                break

        # If no R2 file found, this is single-end reads
        if not r2_file:
            return None

        # Return the path from the IpFile (set by download_file)
        if r2_file.local_path and r2_file.local_path.exists():
            return r2_file.local_path

        raise FileNotFoundError(
            f"R2 file for sample {self.sample_id} not in cache. "
            "Call await reads.fetch() first to download files."
        )

    @classmethod
    async def pinata_hydrate(
        cls,
        sample_id: str,
        **filters,
    ) -> Self:
        """
        Hydrate Reads from Pinata using multi-dimensional metadata queries.

        Supports cartesian product queries when any filter is a list.
        Always queries with type="reads" prefix.

        Args:
            sample_id: Sample identifier
            **filters: Metadata filters (e.g., read_type="paired", sequencing_platform="ILLUMINA")

        Returns:
            Reads instance with IpFile objects

        Raises:
            ValueError: If no files match any of the query combinations

        Example:
            # Query for paired-end ILLUMINA reads
            reads = await Reads.pinata_hydrate(
                sample_id="NA12829",
                read_type="paired",
                sequencing_platform="ILLUMINA"
            )

            # Multi-dimensional query
            reads = await Reads.pinata_hydrate(
                sample_id="NA12829",
                read_type=["paired", "single"]
            )
        """
        # Generate query combinations using cartesian product for list-valued filters
        query_combinations = generate_query_combinations(
            base_query={"type": "reads", "sample_id": sample_id},
            filters=filters,
        )

        # Execute all queries and collect results
        all_files = []
        for query in query_combinations:
            files = await default_client.query_files(query)
            all_files.extend(files)

        if not all_files:
            raise ValueError(
                f"No files found matching queries. sample_id={sample_id}, filters={filters}"
            )

        # Create Reads instance with the files
        return cls(sample_id=sample_id, files=all_files)
