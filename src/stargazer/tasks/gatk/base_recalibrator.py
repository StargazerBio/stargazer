"""
### base_recalibrator task for Stargazer.

Creates BQSR recalibration table using GATK BaseRecalibrator.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from stargazer.assets import Alignment, BQSRReport, KnownSites, Reference
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, scratch_dir


@gatk_env.task
async def base_recalibrator(
    alignment: Alignment,
    ref: Reference,
    known_sites: list[KnownSites],
) -> BQSRReport:
    """
    Generate a Base Quality Score Recalibration report.

    Uses GATK BaseRecalibrator to analyze patterns of covariation in the
    sequence dataset and produce a recalibration table.

    Args:
        alignment: Input BAM asset (should be sorted and have duplicates marked)
        ref: Reference FASTA asset
        known_sites: List of KnownSites VCF assets (dbSNP, known indels, etc.)

    Returns:
        BQSRReport asset containing the recalibration table

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator
    """
    if not known_sites:
        raise ValueError("known_sites list cannot be empty for BQSR")

    # fetch() auto-downloads companions (.fai, .dict, .bai, etc.)
    bam_path = await alignment.fetch()
    ref_path = await ref.fetch()
    site_paths = [await site.fetch() for site in known_sites]

    output_dir = scratch_dir()
    output_recal = output_dir / f"{alignment.sample_id}_bqsr.table"

    cmd = [
        "gatk",
        "BaseRecalibrator",
        "-R",
        str(ref_path),
        "-I",
        str(bam_path),
        "-O",
        str(output_recal),
    ]
    for site_path in site_paths:
        cmd.extend(["--known-sites", str(site_path)])

    await run(cmd, cwd=str(output_dir))

    report = await BQSRReport.store(
        output_recal,
        sample_id=alignment.sample_id,
        tool="gatk_base_recalibrator",
        alignment_cid=alignment.cid,
    )

    return report
