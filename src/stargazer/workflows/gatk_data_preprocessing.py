"""
# GATK Best Practices: Data Pre-processing for Variant Discovery

Implements:
1. Reference preparation — FASTA index, sequence dictionary, BWA index
2. Sample preprocessing — align, sort, mark duplicates, BQSR

References:
    - https://gatk.broadinstitute.org/hc/en-us/articles/360035535912-Data-pre-processing-for-variant-discovery

spec: [docs/architecture/workflows.md](../architecture/workflows.md)
"""

from stargazer.config import gatk_env
from stargazer.types import Alignment, KnownSites, R1, R2, Reference
from stargazer.types.asset import assemble
from stargazer.tasks import (
    samtools_faidx,
    bwa_index,
    bwa_mem,
    sort_sam,
    mark_duplicates,
    base_recalibrator,
    apply_bqsr,
)


@gatk_env.task
async def prepare_reference(build: str) -> Reference:
    """
    Prepare reference genome for alignment and variant calling.

    Assembles the reference FASTA from storage and creates necessary indices:
    1. FASTA index (samtools faidx)
    2. BWA index (bwa index)

    All indices are uploaded to storage as side-effects.

    Args:
        build: Reference genome build identifier (e.g. "GRCh38")

    Returns:
        Reference asset (FASTA file)
    """
    assets = await assemble(build=build, asset="reference")
    refs = [a for a in assets if isinstance(a, Reference)]
    if not refs:
        raise ValueError(f"No reference found for build={build!r}")
    ref = refs[0]

    await samtools_faidx(ref)
    await bwa_index(ref)

    return ref


@gatk_env.task
async def preprocess_sample(
    build: str,
    sample_id: str,
    run_bqsr: bool = True,
) -> Alignment:
    """
    Pre-process a single sample's reads for variant calling.

    Assembles reference and reads from storage, then runs:
    1. BWA-MEM alignment
    2. Coordinate sort (GATK SortSam)
    3. Mark duplicates (GATK MarkDuplicates)
    4. BQSR (optional, GATK BaseRecalibrator + ApplyBQSR)

    Args:
        build: Reference genome build identifier
        sample_id: Sample identifier used to query reads and known sites
        run_bqsr: Whether to apply BQSR (default: True)

    Returns:
        Alignment asset with the preprocessed BAM file
    """
    # Assemble reference
    ref_assets = await assemble(build=build, asset="reference")
    refs = [a for a in ref_assets if isinstance(a, Reference)]
    if not refs:
        raise ValueError(f"No reference found for build={build!r}")
    ref = refs[0]

    # Assemble reads
    read_assets = await assemble(sample_id=sample_id, asset=["r1", "r2"])
    r1_list = [a for a in read_assets if isinstance(a, R1)]
    if not r1_list:
        raise ValueError(f"No R1 reads found for sample_id={sample_id!r}")
    r1 = r1_list[0]
    r2_list = [a for a in read_assets if isinstance(a, R2)]
    r2 = r2_list[0] if r2_list else None

    # Alignment pipeline — tasks call fetch() internally
    alignment = await bwa_mem(ref=ref, r1=r1, r2=r2)
    alignment = await sort_sam(alignment=alignment, sort_order="coordinate")
    alignment = await mark_duplicates(alignment=alignment)

    if run_bqsr:
        known_assets = await assemble(build=build, asset="known_sites")
        known_sites = [a for a in known_assets if isinstance(a, KnownSites)]
        if not known_sites:
            raise ValueError(
                f"run_bqsr=True but no known_sites found for build={build!r}"
            )

        bqsr_report = await base_recalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=known_sites,
        )
        alignment = await apply_bqsr(
            alignment=alignment,
            ref=ref,
            bqsr_report=bqsr_report,
        )

    return alignment
