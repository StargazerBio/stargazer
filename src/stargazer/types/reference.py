"""
Reference genome type for Stargazer.

A reference is a directory in IPFS containing reference files.
"""
import tempfile
import shutil
from dataclasses import dataclass, field
from typing import Optional, Self
from pathlib import Path

from flyte.io import Dir

from stargazer.utils.pinata import PinataClient
from stargazer.utils.query import generate_query_combinations


@dataclass
class Reference:
    """
    A reference genome stored as a directory.

    Attributes:
        dir: Directory containing reference files (Flyte Dir or local Path)
        ref_name: Name of the main reference file
        client: Optional PinataClient for IPFS operations
    """

    ref_name: str
    dir: Dir | Path
    client: PinataClient | None = None

    def get_ref_path(self) -> Path:
        """
        Get the local path to the reference file.
        Downloads the directory if needed (for Flyte Dir).

        Returns:
            Absolute path to the reference file
        """
        # Handle Flyte Dir - download if needed
        if isinstance(self.dir, Dir):
            dir_path = Path(self.dir.download_sync())
        else:
            # Handle local Path
            dir_path = Path(self.dir)

        return dir_path.joinpath(self.ref_name).resolve()

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
            ref_name: Name of the reference file in the directory
            **filters: Metadata filters (e.g., build="GRCh38", tool=["fasta", "bwa"])

        Returns:
            Reference instance with files downloaded from Pinata

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
        # Create Reference instance with local directory
        ref = cls(ref_name=ref_name, dir=Path(tempfile.mkdtemp()))
        ref.client = PinataClient()

        # Generate query combinations using cartesian product for list-valued filters
        query_combinations = generate_query_combinations(
            base_query={"type": "reference"},
            filters=filters,
        )

        # Execute all queries and collect results
        all_files = []
        for query in query_combinations:
            files = await ref.client.query_files(query)
            all_files.extend(files)

        if not all_files:
            raise ValueError(
                f"No files found matching queries. Filters: {filters}"
            )

        # Download and hydrate each file into the Reference directory
        for pinata_file in all_files:
            # Download the file from IPFS
            fpath = await ref.client.download_file(pinata_file.cid)
            shutil.move(fpath, ref.dir / pinata_file.name)

        return ref