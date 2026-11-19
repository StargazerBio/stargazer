"""
### GATK Best Practices: Data Pre-processing for Variant Discovery

Implements:
1. Reference preparation — FASTA index, sequence dictionary, BWA-MEM2 index, each built only if the reference lacks it
2. Sample preprocessing — align, sort, mark duplicates

References:
    - https://gatk.broadinstitute.org/hc/en-us/articles/360035535912-Data-pre-processing-for-variant-discovery

spec: [docs/architecture/workflows.md](../architecture/workflows.md)
"""

from stargazer.assets import R1, R2, Alignment, Reference
from stargazer.tasks import (
    bwa_mem2_index,
    bwa_mem2_mem,
    create_sequence_dictionary,
    mark_duplicates,
    samtools_faidx,
    sort_sam,
)
from stargazer.tasks.gatk.env import gatk_env
from stargazer.tasks.general.bwa_mem2 import BWA_MEM2_INDEX_EXTENSIONS


@gatk_env.task
async def prepare_reference(build: str) -> Reference:
    """
    Prepare reference genome for alignment and variant calling.

    Assembles the reference FASTA from storage and creates the indices it
    lacks:
    1. FASTA index (samtools faidx)
    2. Sequence dictionary (GATK CreateSequenceDictionary)
    3. BWA-MEM2 index (bwa-mem2 index)

    Each index is built only when fetching the reference doesn't bring one
    in as a companion, the user's own or a public one from its publisher, so
    an index built once is reused. Each is stored as a companion of the reference, so
    fetching the reference brings them along.

    Args:
        build: Reference genome build identifier (e.g. "GRCh38")

    Returns:
        Reference asset (FASTA file)
    """
    ref = await Reference.find(build=build)

    # Fetching brings the reference's companions in beside it, so what's
    # missing on disk is what has to be built.
    ref_path = await ref.fetch()
    if not ref_path.with_name(f"{ref_path.name}.fai").exists():
        await samtools_faidx(ref)
    if not ref_path.with_suffix(".dict").exists():
        await create_sequence_dictionary(ref)
    if not all(
        ref_path.with_name(ref_path.name + ext).exists()
        for ext in BWA_MEM2_INDEX_EXTENSIONS
    ):
        await bwa_mem2_index(ref)

    return ref


@gatk_env.task
async def preprocess_sample(
    build: str,
    sample_id: str,
) -> Alignment:
    """
    Pre-process a single sample's reads for variant calling.

    Assembles reference and reads from storage, then runs:
    1. BWA-MEM2 alignment
    2. Coordinate sort (GATK SortSam)
    3. Mark duplicates (GATK MarkDuplicates)

    Args:
        build: Reference genome build identifier
        sample_id: Sample identifier used to query reads

    Returns:
        Alignment asset with the preprocessed BAM file
    """
    ref = await Reference.find(build=build)
    r1 = await R1.find(sample_id=sample_id)
    r2 = await R2.find(sample_id=sample_id, required=False)

    alignment = await bwa_mem2_mem(ref=ref, r1=r1, r2=r2)
    alignment = await sort_sam(alignment=alignment, sort_order="coordinate")
    alignment = await mark_duplicates(alignment=alignment)

    return alignment
