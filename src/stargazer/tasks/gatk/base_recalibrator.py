"""
base_recalibrator task for Stargazer.

Creates BQSR recalibration table using GATK BaseRecalibrator.
"""

from stargazer.config import gatk_env
from stargazer.types import Reference, Alignment
from stargazer.utils import _run
from stargazer.utils.storage import default_client
from stargazer.utils.ipfile import IpFile


@gatk_env.task
async def base_recalibrator(
    alignment: Alignment,
    ref: Reference,
    known_sites: list[str],
) -> IpFile:
    """
    Generate a Base Quality Score Recalibration report.

    Uses GATK BaseRecalibrator to analyze patterns of covariation in the
    sequence dataset and produce a recalibration table for use with applybqsr.

    Args:
        alignment: Input BAM file (should be sorted and have duplicates marked)
        ref: Reference genome with FASTA index
        known_sites: List of known variant VCF files (dbSNP, known indels, etc.)
                    These should be filenames stored in Pinata with type="known_sites"

    Returns:
        IpFile containing the BQSR recalibration report

    Example:
        ref = await prepare_reference(ref_name="GRCh38.fa")
        alignment = await mark_duplicates(alignment=alignment, ref=ref)
        recal_report = await base_recalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=["dbsnp_146.hg38.vcf.gz", "Mills_and_1000G_gold_standard.indels.hg38.vcf.gz"],
        )
        recalibrated_bam = await applybqsr(
            alignment=alignment,
            ref=ref,
            recal_report=recal_report,
        )

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator
    """
    if not known_sites:
        raise ValueError("known_sites list cannot be empty for BQSR")

    # Fetch alignment and reference to cache
    await alignment.fetch()
    await ref.fetch()

    # Get paths
    if not ref.fasta or not ref.fasta.local_path:
        raise ValueError("Reference FASTA file not available or not fetched")
    ref_path = ref.fasta.local_path

    if not alignment.alignment or not alignment.alignment.local_path:
        raise ValueError("Alignment BAM file not available or not fetched")
    bam_path = alignment.alignment.local_path

    output_dir = ref_path.parent

    # Fetch known sites VCFs to cache
    known_sites_paths = []
    for site_name in known_sites:
        # Query for the known sites VCF file
        files = await default_client.query_files(
            {
                "type": "known_sites",
                "name": site_name,
            }
        )

        if not files:
            # Try alternate query with just the name
            files = await default_client.query_files({"name": site_name})

        if not files:
            raise ValueError(f"Known sites file not found: {site_name}")

        # Download the file
        site_file = files[0]
        await default_client.download_file(site_file)
        known_sites_paths.append(site_file.local_path)

    # Output recalibration report path
    output_recal = output_dir / f"{alignment.sample_id}_bqsr.table"

    # Build GATK BaseRecalibrator command
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

    # Add known sites (can specify multiple times)
    for site_path in known_sites_paths:
        cmd.extend(["--known-sites", str(site_path)])

    # Execute BaseRecalibrator
    await _run(cmd, cwd=str(output_dir))

    # Verify output was created
    if not output_recal.exists():
        raise FileNotFoundError(
            f"BaseRecalibrator did not create recalibration report at {output_recal}"
        )

    # Upload recalibration report to Pinata
    keyvalues = {
        "type": "bqsr_report",
        "sample_id": alignment.sample_id,
        "tool": "gatk_base_recalibrator",
    }

    recal_ipfile = await default_client.upload_file(output_recal, keyvalues=keyvalues)
    recal_ipfile.local_path = output_recal

    return recal_ipfile
