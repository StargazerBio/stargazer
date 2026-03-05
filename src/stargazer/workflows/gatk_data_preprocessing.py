"""
GATK Best Practices: Data Pre-processing for Variant Discovery

Implements:
1. Reference preparation — FASTA index, sequence dictionary, BWA index
2. Sample preprocessing — align, sort, mark duplicates, BQSR

References:
    - https://gatk.broadinstitute.org/hc/en-us/articles/360035535912-Data-pre-processing-for-variant-discovery
"""

import stargazer.utils.storage as _storage
from stargazer.config import gatk_env
from stargazer.types import Alignment, AlignerIndex, KnownSites, Reference
from stargazer.types.constellation import assemble
from stargazer.tasks import (
    samtools_faidx,
    create_sequence_dictionary,
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
    2. Sequence dictionary (GATK CreateSequenceDictionary)
    3. BWA index (bwa index)

    All indices are uploaded to storage as side-effects.

    Args:
        build: Reference genome build identifier (e.g. "GRCh38")

    Returns:
        Reference asset (FASTA file)
    """
    c = await assemble(build=build, asset="reference")
    ref = c.reference
    if ref is None:
        raise ValueError(f"No reference found for build={build!r}")

    await _storage.default_client.download(ref)

    await samtools_faidx(ref)
    await create_sequence_dictionary(ref)
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
    # Assemble reference assets
    c_ref = await assemble(build=build, asset=["reference", "aligner_index"])
    ref = c_ref.reference
    if ref is None:
        raise ValueError(f"No reference found for build={build!r}")
    await _storage.default_client.download(ref)

    raw_indices = c_ref.aligner_index
    if raw_indices is None:
        raise ValueError(f"No aligner_index found for build={build!r}")
    aligner_indices: list[AlignerIndex] = (
        raw_indices if isinstance(raw_indices, list) else [raw_indices]
    )
    for idx in aligner_indices:
        await _storage.default_client.download(idx)

    # Assemble reads
    c_reads = await assemble(sample_id=sample_id, asset=["r1", "r2"])
    r1 = c_reads.r1
    r2 = c_reads.r2  # May be None for single-end
    if r1 is None:
        raise ValueError(f"No R1 reads found for sample_id={sample_id!r}")
    await _storage.default_client.download(r1)
    if r2 is not None:
        await _storage.default_client.download(r2)

    # Alignment pipeline
    alignment = await bwa_mem(ref=ref, r1=r1, r2=r2, aligner_indices=aligner_indices)
    alignment = await sort_sam(alignment=alignment, sort_order="coordinate")
    alignment = await mark_duplicates(alignment=alignment)

    if run_bqsr:
        c_known = await assemble(build=build, asset="known_sites")
        raw_known = c_known.known_sites
        if raw_known is None:
            raise ValueError(
                f"run_bqsr=True but no known_sites found for build={build!r}"
            )
        known_sites: list[KnownSites] = (
            raw_known if isinstance(raw_known, list) else [raw_known]
        )
        for site in known_sites:
            await _storage.default_client.download(site)

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
