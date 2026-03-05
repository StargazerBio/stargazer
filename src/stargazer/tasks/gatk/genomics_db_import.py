"""
GenomicsDBImport task for Stargazer.

Import VCFs to GenomicsDB for efficient joint genotyping of large cohorts.
"""

from pathlib import Path

from stargazer.config import gatk_env
from stargazer.types import Variants
from stargazer.utils import _run


@gatk_env.task
async def genomics_db_import(
    gvcfs: list[Variants],
    workspace_path: Path,
    intervals: list[str] | None = None,
) -> Path:
    """
    Import GVCFs to GenomicsDB workspace for scalable joint genotyping.

    Args:
        gvcfs: List of per-sample GVCF Variants assets to import
        workspace_path: Path where GenomicsDB workspace will be created
        intervals: Genomic intervals to process (e.g., ["chr1", "chr2:100000-200000"])

    Returns:
        Path to the created GenomicsDB workspace directory

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360036883491-GenomicsDBImport
    """
    if not gvcfs:
        raise ValueError("At least one GVCF must be provided")

    for gvcf in gvcfs:
        if gvcf.variant_type != "gvcf":
            raise ValueError(
                f"All inputs must be GVCFs, got variant_type={gvcf.variant_type!r}: "
                f"sample_id={gvcf.sample_id}"
            )

    if workspace_path.exists():
        raise ValueError(
            f"GenomicsDB workspace already exists at {workspace_path}. "
            "Use --genomicsdb-update-workspace-path to add samples to existing workspace."
        )

    for gvcf in gvcfs:
        await gvcf.fetch()

    sample_map_path = workspace_path.parent / "sample_map.txt"
    sample_map_path.parent.mkdir(parents=True, exist_ok=True)

    with open(sample_map_path, "w") as f:
        for gvcf in gvcfs:
            if not gvcf.path:
                raise ValueError(
                    f"GVCF file not available for sample_id={gvcf.sample_id}"
                )
            f.write(f"{gvcf.sample_id}\t{gvcf.path}\n")

    cmd = [
        "gatk",
        "GenomicsDBImport",
        "--genomicsdb-workspace-path",
        str(workspace_path),
        "--sample-name-map",
        str(sample_map_path),
    ]

    if intervals:
        for interval in intervals:
            cmd.extend(["-L", interval])

    await _run(cmd, cwd=str(workspace_path.parent))

    if not workspace_path.exists():
        raise FileNotFoundError(
            f"GenomicsDBImport did not create workspace at {workspace_path}"
        )

    return workspace_path
