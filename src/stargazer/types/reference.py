"""
Reference genome type for Stargazer.

A reference is a collection of files stored in IPFS.
"""
import tempfile
from dataclasses import dataclass, field
from typing import Self
from pathlib import Path

from stargazer.utils.pinata import PinataClient, IpFile
from stargazer.utils.query import generate_query_combinations


@dataclass
class Reference:
    """
    A reference genome stored as IPFS files.

    Attributes:
        ref_name: Name of the main reference file
        files: List of IpFile objects containing reference data
        client: PinataClient for IPFS operations (initialized on first use)
    """

    ref_name: str
    files: list[IpFile] = field(default_factory=list)
    client: PinataClient = field(default_factory=PinataClient)

    async def add_files(
        self,
        file_paths: list[Path],
        keyvalues: dict[str, str] | None = None,
    ) -> None:
        """
        Upload files and add to reference.

        Uploads files to IPFS (or copies to local cache if STARGAZER_LOCAL_ONLY is set)
        and adds the resulting IpFile objects to this reference's files list.

        Args:
            file_paths: List of local file paths to upload
            keyvalues: Optional metadata key-value pairs to attach to all files

        Raises:
            FileNotFoundError: If any file path doesn't exist
            ValueError: If file_paths is empty

        Example:
            # Upload to IPFS (default)
            ref = Reference(ref_name="genome.fa")
            await ref.add_files(
                file_paths=[Path("genome.fa"), Path("genome.fa.fai")],
                keyvalues={"type": "reference", "build": "GRCh38", "tool": "fasta"}
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
            ipfile = await self.client.upload_file(path, keyvalues=keyvalues)
            self.files.append(ipfile)

    async def fetch(self) -> Path:
        """
        Fetch all reference files to local cache.

        Downloads all files in the reference to the PinataClient cache.
        Returns the cache directory containing all files.

        Returns:
            Path to cache directory containing all reference files

        Example:
            ref = await Reference.pinata_hydrate(ref_name="genome.fa", build="GRCh38")
            cache_dir = await ref.fetch()
            # All files now in cache_dir
        """
        if not self.files:
            raise ValueError("No files to fetch. Reference is empty.")

        # Download all files to cache and update their paths
        for ipfile in self.files:
            await self.client.download_file(ipfile)

        # Return the cache directory
        # All files are cached at client.cache_dir / cid
        # We'll return a directory that contains all our files
        return self.client.cache_dir

    def get_ref_path(self) -> Path:
        """
        Get the local cached path to the reference file.

        The reference must be fetched first using fetch().

        Returns:
            Absolute path to the cached reference file

        Raises:
            FileNotFoundError: If file not found in cache (need to fetch first)
        """
        # Find the reference file by name
        ref_file = None
        for f in self.files:
            if f.name == self.ref_name:
                ref_file = f
                break

        if not ref_file:
            raise FileNotFoundError(
                f"Reference file {self.ref_name} not found in files list"
            )

        # Return cached path
        cache_path = self.client.cache_dir / ref_file.cid
        if cache_path.exists():
            return cache_path

        raise FileNotFoundError(
            f"Reference file {self.ref_name} not in cache. "
            "Call await ref.fetch() first to download files."
        )

    def get_file_path(self, filename: str) -> Path:
        """
        Get the local cached path to any file in the reference.

        Args:
            filename: Name of the file to get path for

        Returns:
            Absolute path to the cached file

        Raises:
            FileNotFoundError: If file not found
        """
        # Find the file by name
        target_file = None
        for f in self.files:
            if f.name == filename:
                target_file = f
                break

        if not target_file:
            raise FileNotFoundError(
                f"File {filename} not found in files list"
            )

        # Return cached path
        cache_path = self.client.cache_dir / target_file.cid
        if cache_path.exists():
            return cache_path

        raise FileNotFoundError(
            f"File {filename} not in cache. "
            "Call await ref.fetch() first to download files."
        )

    @classmethod
    async def pinata_hydrate(
        cls,
        ref_name: str,
        **filters,
    ) -> Self:
        """
        Hydrate Reference from Pinata using multi-dimensional metadata queries.

        Supports cartesian product queries when any filter is a list.
        Always queries with type="reference" prefix.

        Args:
            ref_name: Name of the reference file
            **filters: Metadata filters (e.g., build="GRCh38", tool=["fasta", "bwa"])

        Returns:
            Reference instance with IpFile objects

        Raises:
            ValueError: If no files match any of the query combinations

        Example:
            # Single query
            ref = await Reference.pinata_hydrate(
                ref_name="genome.fa",
                build="GRCh38",
                tool="fasta"
            )

            # Multi-dimensional query (produces 3 queries for tool list)
            ref = await Reference.pinata_hydrate(
                ref_name="genome.fa",
                build="GRCh38",
                tool=["fasta", "faidx", "bwa"]
            )
        """
        # Create client
        client = PinataClient()

        # Generate query combinations using cartesian product for list-valued filters
        query_combinations = generate_query_combinations(
            base_query={"type": "reference"},
            filters=filters,
        )

        # Execute all queries and collect results
        all_files = []
        for query in query_combinations:
            files = await client.query_files(query)
            all_files.extend(files)

        if not all_files:
            raise ValueError(
                f"No files found matching queries. Filters: {filters}"
            )

        # Create Reference instance with the files
        return cls(ref_name=ref_name, files=all_files, client=client)
