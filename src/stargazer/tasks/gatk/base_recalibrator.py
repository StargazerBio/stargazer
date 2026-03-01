"""
base_recalibrator task for Stargazer.

Creates BQSR recalibration table using GATK BaseRecalibrator.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Alignment, KnownSites
from stargazer.types.alignment import BQSRReport
from stargazer.utils import _run


@gatk_env.task
async def base_recalibrator(
    alignment: Alignment,
    ref: Reference,
    known_sites: list[KnownSites],
) -> Alignment:
    """
    Generate a Base Quality Score Recalibration report.

    Uses GATK BaseRecalibrator to analyze patterns of covariation in the
    sequence dataset and produce a recalibration table. Returns the same
    Alignment with bqsr_report populated, ready to pass directly to apply_bqsr.

    Args:
        alignment: Input BAM file (should be sorted and have duplicates marked)
        ref: Reference genome with FASTA index
        known_sites: List of KnownSites VCFs for known variant sites (dbSNP, known indels, etc.)

    Returns:
        Alignment with bqsr_report set

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator
    """
    import stargazer.utils.storage as _storage

    if not known_sites:
        raise ValueError("known_sites list cannot be empty for BQSR")

    await alignment.fetch()
    await ref.fetch()

    if not ref.fasta or not ref.fasta.path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.path

    if not alignment.alignment or not alignment.alignment.path:
        raise ValueError("Alignment BAM file not available or not fetched")
    bam_path = alignment.alignment.path

    output_dir = _storage.default_client.local_dir

    known_sites_paths = []
    for site in known_sites:
        await _storage.default_client.download(site)
        known_sites_paths.append(site.path)

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
    for site_path in known_sites_paths:
        cmd.extend(["--known-sites", str(site_path)])

    await _run(cmd, cwd=str(output_dir))

    if not output_recal.exists():
        raise FileNotFoundError(
            f"BaseRecalibrator did not create recalibration report at {output_recal}"
        )

    report = BQSRReport()
    await report.update(
        output_recal, sample_id=alignment.sample_id, tool="gatk_base_recalibrator"
    )

    return Alignment(
        sample_id=alignment.sample_id,
        alignment=alignment.alignment,
        index=alignment.index,
        bqsr_report=report,
    )
