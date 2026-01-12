"""
Alignment type for Stargazer.

Represents aligned BAM/CRAM files stored in IPFS.
"""

from dataclasses import dataclass, field
from typing import Self
from pathlib import Path

from stargazer.utils.pinata import default_client, IpFile
from stargazer.utils.query import generate_query_combinations


@dataclass
class Alignment:
    """
    Aligned BAM/CRAM files stored as IPFS files.

    Attributes:
        sample_id: Sample identifier
        bam_name: Name of the main BAM/CRAM file
        files: List of IpFile objects containing BAM + optional BAI index + optional metrics

    Properties:
        has_duplicates_marked: Whether duplicates are marked (read from BAM file keyvalues)
        is_sorted: Whether reads are coordinate sorted (read from BAM file keyvalues)
    """

    sample_id: str
    bam_name: str
    files: list[IpFile] = field(default_factory=list)

    @property
    def has_duplicates_marked(self) -> bool:
        """
        Whether duplicates are marked in the BAM file.

        Reads from the BAM file's keyvalues metadata.

        Returns:
            True if duplicates_marked="true" in BAM file keyvalues, False otherwise
        """
        # Find the BAM file and check its metadata
        for f in self.files:
            if f.name == self.bam_name:
                return f.keyvalues.get("duplicates_marked") == "true"
        return False

    @property
    def is_sorted(self) -> bool:
        """
        Whether the BAM file is coordinate sorted.

        Reads from the BAM file's keyvalues metadata.

        Returns:
            True if sorted="coordinate" in BAM file keyvalues, False otherwise
        """
        # Find the BAM file and check its metadata
        for f in self.files:
            if f.name == self.bam_name:
                return f.keyvalues.get("sorted") == "coordinate"
        return False

    @property
    def has_bqsr_applied(self) -> bool:
        """
        Whether Base Quality Score Recalibration has been applied.

        Reads from the BAM file's keyvalues metadata.

        Returns:
            True if bqsr_applied="true" in BAM file keyvalues, False otherwise
        """
        # Find the BAM file and check its metadata
        for f in self.files:
            if f.name == self.bam_name:
                return f.keyvalues.get("bqsr_applied") == "true"
        return False

    async def add_files(
        self,
        file_paths: list[Path],
        keyvalues: dict[str, str] | None = None,
    ) -> None:
        """
        Upload alignment files and add to this object.

        Uploads files to IPFS (or copies to local cache if STARGAZER_LOCAL_ONLY is set)
        and adds the resulting IpFile objects to this alignment's files list.

        Args:
            file_paths: List of local file paths to upload (BAM, BAI, etc.)
            keyvalues: Optional metadata key-value pairs to attach to all files

        Raises:
            FileNotFoundError: If any file path doesn't exist
            ValueError: If file_paths is empty

        Example:
            alignment = Alignment(sample_id="NA12829", bam_name="aligned.bam")
            await alignment.add_files(
                file_paths=[Path("aligned.bam"), Path("aligned.bam.bai")],
                keyvalues={
                    "type": "alignment",
                    "sample_id": "NA12829",
                    "tool": "fq2bam",
                    "file_type": "bam",
                    "sorted": "coordinate",
                    "duplicates_marked": "true"
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
            # Preserve local_path so the file remains accessible without re-downloading
            ipfile.local_path = path.resolve()
            self.files.append(ipfile)

    async def fetch(self) -> Path:
        """
        Fetch all alignment files to local cache.

        Downloads all files in the alignment to the PinataClient cache.
        Returns the cache directory containing all files.

        Returns:
            Path to cache directory containing all alignment files

        Raises:
            ValueError: If no files to fetch (alignment is empty)

        Example:
            alignment = await Alignment.pinata_hydrate(
                sample_id="NA12829",
                bam_name="aligned.bam"
            )
            cache_dir = await alignment.fetch()
            # All alignment files now in cache_dir
        """
        if not self.files:
            raise ValueError("No files to fetch. Alignment is empty.")

        # Download all files to cache and update their paths
        for ipfile in self.files:
            await default_client.download_file(ipfile)

        # Return the cache directory
        return default_client.cache_dir

    def get_bam_path(self) -> Path:
        """
        Get the local cached path to the BAM/CRAM file.

        The alignment must be fetched first using fetch().

        Returns:
            Absolute path to the cached BAM/CRAM file

        Raises:
            FileNotFoundError: If BAM file not found or not in cache
        """
        # Find the BAM file by name
        bam_file = None
        for f in self.files:
            if f.name == self.bam_name:
                bam_file = f
                break

        if not bam_file:
            raise FileNotFoundError(f"BAM file {self.bam_name} not found in files list")

        # Return the path from the IpFile (set by download_file)
        if bam_file.local_path and bam_file.local_path.exists():
            return bam_file.local_path

        raise FileNotFoundError(
            f"BAM file {self.bam_name} not in cache. "
            "Call await alignment.fetch() first to download files."
        )

    def get_bai_path(self) -> Path | None:
        """
        Get the local cached path to the BAM index file.

        Returns None if no index file is present.

        Returns:
            Absolute path to the cached BAI file, or None if not present

        Raises:
            FileNotFoundError: If BAI file exists but not in cache
        """
        # Find the BAI file by name pattern (bam_name + .bai)
        bai_name = f"{self.bam_name}.bai"
        bai_file = None
        for f in self.files:
            if f.name == bai_name:
                bai_file = f
                break

        # If no BAI file found, return None
        if not bai_file:
            return None

        # Return the path from the IpFile (set by download_file)
        if bai_file.local_path and bai_file.local_path.exists():
            return bai_file.local_path

        raise FileNotFoundError(
            f"BAI file {bai_name} not in cache. "
            "Call await alignment.fetch() first to download files."
        )

    @classmethod
    async def pinata_hydrate(
        cls,
        sample_id: str,
        bam_name: str,
        **filters,
    ) -> Self:
        """
        Hydrate Alignment from Pinata using multi-dimensional metadata queries.

        Supports cartesian product queries when any filter is a list.
        Always queries with type="alignment" prefix.

        Args:
            sample_id: Sample identifier
            bam_name: Name of the BAM file
            **filters: Metadata filters (e.g., tool="fq2bam", sorted="coordinate")

        Returns:
            Alignment instance with IpFile objects

        Raises:
            ValueError: If no files match any of the query combinations

        Example:
            # Query for sorted, duplicate-marked BAM
            alignment = await Alignment.pinata_hydrate(
                sample_id="NA12829",
                bam_name="aligned.bam",
                tool="fq2bam",
                sorted="coordinate",
                duplicates_marked="true"
            )

            # Multi-dimensional query
            alignment = await Alignment.pinata_hydrate(
                sample_id="NA12829",
                bam_name="aligned.bam",
                tool=["fq2bam", "bwa"]
            )
        """
        # Generate query combinations using cartesian product for list-valued filters
        query_combinations = generate_query_combinations(
            base_query={"type": "alignment", "sample_id": sample_id},
            filters=filters,
        )

        # Execute all queries and collect results
        all_files = []
        for query in query_combinations:
            files = await default_client.query_files(query)
            all_files.extend(files)

        if not all_files:
            raise ValueError(
                f"No files found matching queries. "
                f"sample_id={sample_id}, bam_name={bam_name}, filters={filters}"
            )

        # Create Alignment instance with the files
        # Note: has_duplicates_marked and is_sorted are now properties
        # that read from the BAM file's keyvalues
        return cls(
            sample_id=sample_id,
            bam_name=bam_name,
            files=all_files,
        )
