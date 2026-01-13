"""
GenomicsDBImport task for Stargazer.

Import VCFs to GenomicsDB for efficient joint genotyping of large cohorts.
"""

from pathlib import Path

from stargazer.config import pb_env
from stargazer.types import Variants
from stargazer.utils import _run


@pb_env.task
async def genomicsdbimport(
    gvcfs: list[Variants],
    workspace_path: Path,
    intervals: list[str] | None = None,
    batch_size: int = 50,
) -> Path:
    """
    Import GVCFs to GenomicsDB workspace for scalable joint genotyping.

    GenomicsDBImport is the recommended alternative to CombineGVCFs for cohorts
    with more than ~100 samples. It creates a GenomicsDB workspace that can be
    efficiently queried by GenotypeGVCFs.

    Args:
        gvcfs: List of per-sample GVCF Variants objects to import
        workspace_path: Path where GenomicsDB workspace will be created
        intervals: Genomic intervals to process (e.g., ["chr1", "chr2:100000-200000"])
        batch_size: Number of samples to import at once (default: 50, reduces memory)

    Returns:
        Path to the created GenomicsDB workspace directory

    Raises:
        ValueError: If no GVCFs provided or workspace already exists
        FileNotFoundError: If workspace creation fails

    Example:
        # Import GVCFs for large cohort
        workspace = await genomicsdbimport(
            gvcfs=all_gvcfs,  # List of 1000+ GVCF objects
            workspace_path=Path("/data/cohort_db"),
            intervals=["chr1", "chr2"],
            batch_size=50,
        )

        # Then use with GenotypeGVCFs
        joint_vcf = await genotypegvcf_from_genomicsdb(
            genomicsdb_workspace=workspace,
            ref=ref,
        )

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360036883491-GenomicsDBImport
        https://gatk.broadinstitute.org/hc/en-us/articles/360035890531-GenomicsDB
    """
    if not gvcfs:
        raise ValueError("At least one GVCF must be provided")

    # Check all inputs are GVCFs
    for gvcf in gvcfs:
        if not gvcf.is_gvcf:
            raise ValueError(f"All inputs must be GVCFs, got VCF: {gvcf.vcf_name}")

    # Workspace must not exist
    if workspace_path.exists():
        raise ValueError(
            f"GenomicsDB workspace already exists at {workspace_path}. "
            f"Use --genomicsdb-update-workspace-path to add samples to existing workspace."
        )

    # Fetch all GVCFs
    for gvcf in gvcfs:
        await gvcf.fetch()

    # Create sample map file (required by GenomicsDB)
    sample_map_path = workspace_path.parent / "sample_map.txt"
    sample_map_path.parent.mkdir(parents=True, exist_ok=True)

    with open(sample_map_path, "w") as f:
        for gvcf in gvcfs:
            gvcf_path = gvcf.get_vcf_path()
            f.write(f"{gvcf.sample_id}\t{gvcf_path}\n")

    # Build command
    cmd = [
        "gatk",
        "GenomicsDBImport",
        "--genomicsdb-workspace-path",
        str(workspace_path),
        "--sample-name-map",
        str(sample_map_path),
        "--batch-size",
        str(batch_size),
    ]

    # Add intervals if specified
    if intervals:
        for interval in intervals:
            cmd.extend(["-L", interval])

    # Execute
    await _run(cmd, cwd=str(workspace_path.parent))

    # Verify workspace was created
    if not workspace_path.exists():
        raise FileNotFoundError(
            f"GenomicsDBImport did not create workspace at {workspace_path}"
        )

    return workspace_path
