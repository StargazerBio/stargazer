"""
Reference genome type for Stargazer.

A reference is a directory in IPFS containing reference files.
"""
import tempfile
import shutil
from dataclasses import dataclass
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
        dir: Flyte directory containing reference files
        ref_name: ref_name of the main reference file
    """

    dir: Dir
    ref_name: str
    client: Optional[PinataClient] = None

    def get_ref_path(self) -> Path:
        """
        Get the local path to the reference file.
        Downloads the directory if needed.
        """
        dir_path = Path(self.dir.download_sync())
        return dir_path / self.ref_name

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
            ref_name: ref_name of the reference file in the directory
            client: Optional PinataClient instance
            **filters: Metadata filters (e.g., build="GRCh38", tool=["fasta", "bwa"])

        Returns:
            List of Reference instances matching the queries

        Raises:
            ValueError: If no files match any of the query combinations

        Example:
            # Single query
            refs = await Reference.hydrate(
                ref_name="genome.fa",
                build="GRCh38",
                tool="fasta"
            )

            # Multi-dimensional query (produces 3 queries for tool list)
            refs = await Reference.hydrate(
                ref_name="genome.fa",
                build="GRCh38",
                tool=["fasta", "faidx", "bwa"]
            )
        """
        # Create Reference instance
        ref = cls(
            dir=await Dir.from_local(tempfile.mkdtemp()),
            ref_name=ref_name,
        )
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

        # Download and hydrate each file into a Reference
        for pinata_file in all_files:
            # Download the directory from IPFS
            fpath = await ref.client.download_file(pinata_file.cid)
            shutil.move(fpath, Path(ref.dir.path).joinpath(pinata_file.name))

        return ref