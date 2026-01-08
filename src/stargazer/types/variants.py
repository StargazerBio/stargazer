"""
Variants type for Stargazer.

Represents variant calls in VCF/GVCF format stored in IPFS.
"""

from dataclasses import dataclass, field
from typing import Self
from pathlib import Path

from stargazer.utils.pinata import default_client, IpFile
from stargazer.utils.query import generate_query_combinations


@dataclass
class Variants:
    """
    Variant calls in VCF/GVCF format stored as IPFS files.

    Attributes:
        sample_id: Sample identifier
        vcf_name: Name of the VCF file
        files: List of IpFile objects containing VCF + optional index (.tbi)

    Properties:
        caller: Variant caller used (read from VCF file keyvalues)
        is_gvcf: Whether this is a GVCF (read from VCF file keyvalues)
    """

    sample_id: str
    vcf_name: str
    files: list[IpFile] = field(default_factory=list)

    @property
    def caller(self) -> str:
        """
        Variant caller used to generate this VCF.

        Reads from the VCF file's keyvalues metadata.

        Returns:
            Caller name (e.g., "deepvariant", "haplotypecaller") or "unknown"
        """
        # Find the VCF file and check its metadata
        for f in self.files:
            if f.name == self.vcf_name:
                return f.keyvalues.get("caller", "unknown")
        return "unknown"

    @property
    def is_gvcf(self) -> bool:
        """
        Whether this is a GVCF file.

        Reads from the VCF file's keyvalues metadata.

        Returns:
            True if variant_type="gvcf" in VCF file keyvalues, False otherwise
        """
        # Find the VCF file and check its metadata
        for f in self.files:
            if f.name == self.vcf_name:
                return f.keyvalues.get("variant_type") == "gvcf"
        return False

    async def add_files(
        self,
        file_paths: list[Path],
        keyvalues: dict[str, str] | None = None,
    ) -> None:
        """
        Upload variant files and add to this object.

        Uploads files to IPFS (or copies to local cache if STARGAZER_LOCAL_ONLY is set)
        and adds the resulting IpFile objects to this variants' files list.

        Args:
            file_paths: List of local file paths to upload (VCF, TBI, etc.)
            keyvalues: Optional metadata key-value pairs to attach to all files

        Raises:
            FileNotFoundError: If any file path doesn't exist
            ValueError: If file_paths is empty

        Example:
            variants = Variants(sample_id="NA12829", vcf_name="variants.vcf")
            await variants.add_files(
                file_paths=[Path("variants.vcf"), Path("variants.vcf.tbi")],
                keyvalues={
                    "type": "variants",
                    "sample_id": "NA12829",
                    "caller": "deepvariant",
                    "variant_type": "vcf",
                    "build": "GRCh38"
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
        Fetch all variant files to local cache.

        Downloads all files in the variants to the PinataClient cache.
        Returns the cache directory containing all files.

        Returns:
            Path to cache directory containing all variant files

        Raises:
            ValueError: If no files to fetch (variants is empty)

        Example:
            variants = await Variants.pinata_hydrate(
                sample_id="NA12829",
                caller="deepvariant"
            )
            cache_dir = await variants.fetch()
            # All variant files now in cache_dir
        """
        if not self.files:
            raise ValueError("No files to fetch. Variants is empty.")

        # Download all files to cache and update their paths
        for ipfile in self.files:
            await default_client.download_file(ipfile)

        # Return the cache directory
        return default_client.cache_dir

    def get_vcf_path(self) -> Path:
        """
        Get the local cached path to the VCF file.

        The variants must be fetched first using fetch().

        Returns:
            Absolute path to the cached VCF file

        Raises:
            FileNotFoundError: If VCF file not found or not in cache
        """
        # Find the VCF file by name
        vcf_file = None
        for f in self.files:
            if f.name == self.vcf_name:
                vcf_file = f
                break

        if not vcf_file:
            raise FileNotFoundError(f"VCF file {self.vcf_name} not found in files list")

        # Return the path from the IpFile (set by download_file)
        if vcf_file.local_path and vcf_file.local_path.exists():
            return vcf_file.local_path

        raise FileNotFoundError(
            f"VCF file {self.vcf_name} not in cache. "
            "Call await variants.fetch() first to download files."
        )

    def get_index_path(self) -> Path | None:
        """
        Get the local cached path to the VCF index file.

        Returns None if no index file is present.

        Returns:
            Absolute path to the cached TBI file, or None if not present

        Raises:
            FileNotFoundError: If TBI file exists but not in cache
        """
        # Find the TBI file by name pattern (vcf_name + .tbi)
        tbi_name = f"{self.vcf_name}.tbi"
        tbi_file = None
        for f in self.files:
            if f.name == tbi_name:
                tbi_file = f
                break

        # If no TBI file found, return None
        if not tbi_file:
            return None

        # Return the path from the IpFile (set by download_file)
        if tbi_file.local_path and tbi_file.local_path.exists():
            return tbi_file.local_path

        raise FileNotFoundError(
            f"TBI file {tbi_name} not in cache. "
            "Call await variants.fetch() first to download files."
        )

    @classmethod
    async def pinata_hydrate(
        cls,
        sample_id: str,
        **filters,
    ) -> Self:
        """
        Hydrate Variants from Pinata using multi-dimensional metadata queries.

        Supports cartesian product queries when any filter is a list.
        Always queries with type="variants" prefix.

        Args:
            sample_id: Sample identifier
            **filters: Metadata filters (e.g., caller="deepvariant", variant_type="vcf")

        Returns:
            Variants instance with IpFile objects

        Raises:
            ValueError: If no files match any of the query combinations

        Example:
            # Query for DeepVariant VCF
            variants = await Variants.pinata_hydrate(
                sample_id="NA12829",
                caller="deepvariant",
                variant_type="vcf"
            )

            # Multi-dimensional query
            variants = await Variants.pinata_hydrate(
                sample_id="NA12829",
                caller=["deepvariant", "haplotypecaller"]
            )
        """
        # Generate query combinations using cartesian product for list-valued filters
        query_combinations = generate_query_combinations(
            base_query={"type": "variants", "sample_id": sample_id},
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
                f"sample_id={sample_id}, filters={filters}"
            )

        # Find the VCF file (not the index) to use as vcf_name
        vcf_name = None
        for f in all_files:
            if not f.name.endswith(".tbi"):
                vcf_name = f.name
                break

        if not vcf_name:
            raise ValueError("No VCF file found in query results (only index files)")

        # Create Variants instance with the files
        return cls(
            sample_id=sample_id,
            vcf_name=vcf_name,
            files=all_files,
        )
