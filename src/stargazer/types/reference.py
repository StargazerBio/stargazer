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
        client: Optional PinataClient for IPFS operations
    """

    ref_name: str
    files: list[IpFile] = field(default_factory=list)
    client: PinataClient | None = None

    def get_ref_path(self) -> Path:
        """
        Get the local path to the reference file.
        Downloads the file from Pinata if needed.

        Returns:
            Absolute path to the reference file
        """
        # Initialize client if needed
        if not self.client:
            self.client = PinataClient()

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

        # Download and return path (uses client's cache)
        # Note: download_file is async, so we need sync version or make this async
        # For now, use the cache path directly if available
        cache_path = self.client.cache_dir / ref_file.cid / ref_file.name
        if cache_path.exists():
            return cache_path

        raise FileNotFoundError(
            f"Reference file {self.ref_name} not in cache. "
            "Download it first using client.download_file()"
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