"""
AnalyzeCovariates task for Stargazer.

Evaluate and compare base quality score recalibration (BQSR) tables.
"""

from pathlib import Path

from stargazer.config import gatk_env
from stargazer.utils import _run


@gatk_env.task
async def analyze_covariates(
    before_report: Path,
    after_report: Path | None = None,
) -> Path:
    """
    Generate plots to analyze BQSR recalibration quality.

    Creates visualization plots comparing base quality scores before and
    (optionally) after recalibration. This is a QC tool to assess whether
    BQSR improved base quality scores appropriately.

    Args:
        before_report: BQSR recalibration report from BaseRecalibrator (first pass)
        after_report: Optional second-pass report (after applying BQSR) for comparison

    Returns:
        Path to the output PDF plots file

    Raises:
        FileNotFoundError: If report files don't exist or plots aren't generated

    Example:
        # Basic usage (single report)
        recal_report = await base_recalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=known_sites,
        )

        plots = await analyze_covariates(
            before_report=recal_report,
        )

        # Advanced usage (before/after comparison)
        # First pass
        recal_before = await base_recalibrator(
            alignment=raw_bam,
            ref=ref,
            known_sites=known_sites,
        )

        # Apply BQSR
        recal_bam = await apply_bqsr(
            alignment=raw_bam,
            ref=ref,
            recal_report=recal_before,
        )

        # Second pass (optional, for QC)
        recal_after = await base_recalibrator(
            alignment=recal_bam,
            ref=ref,
            known_sites=known_sites,
        )

        # Generate comparison plots
        plots = await analyze_covariates(
            before_report=recal_before,
            after_report=recal_after,
        )

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-AnalyzeCovariates
    """
    if not before_report.exists():
        raise FileNotFoundError(f"Before report not found: {before_report}")

    if after_report and not after_report.exists():
        raise FileNotFoundError(f"After report not found: {after_report}")

    # Output plots file
    output_dir = before_report.parent
    plots_file = output_dir / f"{before_report.stem}_plots.pdf"

    # Build command
    cmd = [
        "gatk",
        "AnalyzeCovariates",
        "-before",
        str(before_report),
        "-plots",
        str(plots_file),
    ]

    # Add after report if provided
    if after_report:
        cmd.extend(["-after", str(after_report)])

    # Execute
    await _run(cmd, cwd=str(output_dir))

    # Verify plots were created
    if not plots_file.exists():
        raise FileNotFoundError(
            f"AnalyzeCovariates did not create plots file at {plots_file}"
        )

    return plots_file
