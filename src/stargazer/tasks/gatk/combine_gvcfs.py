"""
### CombineGVCFs task for Stargazer.

Combines multiple per-sample GVCFs into a single multi-sample GVCF
for joint genotyping using GATK CombineGVCFs.

spec: [docs/architecture/tasks.md](../architecture/tasks.md)
"""

from pathlib import Path

from stargazer.assets import Reference, Variants, VariantsIndex
from stargazer.tasks.gatk.env import gatk_env
from stargazer.utils import run, scratch_dir


@gatk_env.task
async def combine_gvcfs(
    gvcfs: list[Variants],
    ref: Reference,
    cohort_id: str = "cohort",
) -> Variants:
    """
    Combine multiple per-sample GVCFs into a single multi-sample GVCF.

    Args:
        gvcfs: List of Variants assets, each containing a GVCF from a single sample
        ref: Reference FASTA asset
        cohort_id: Identifier for the combined cohort (default: "cohort")

    Returns:
        Variants asset with the combined multi-sample GVCF, linked to the
        input GVCFs

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037053272-CombineGVCFs
    """
    if not gvcfs:
        raise ValueError("gvcfs list cannot be empty")

    for i, gvcf in enumerate(gvcfs):
        if gvcf.variant_type != "gvcf":
            raise ValueError(
                f"combine_gvcfs requires GVCF files, but gvcfs[{i}] is not a GVCF. "
                f"sample_id={gvcf.sample_id}"
            )

    # fetch() auto-downloads companions (.fai, .dict for ref; .idx for each gvcf)
    ref_path = await ref.fetch()

    gvcf_paths: list[Path] = []
    sample_ids: list[str] = []

    for gvcf in gvcfs:
        gvcf_paths.append(await gvcf.fetch())
        sample_ids.append(gvcf.sample_id)

    output_dir = scratch_dir()
    output_gvcf = output_dir / f"{cohort_id}_combined.g.vcf"

    cmd = [
        "gatk",
        "CombineGVCFs",
        "-R",
        str(ref_path),
        "-O",
        str(output_gvcf),
    ]

    for gvcf_path in gvcf_paths:
        cmd.extend(["-V", str(gvcf_path)])

    await run(cmd, cwd=str(output_dir))

    combined_vcf = await Variants.store(
        output_gvcf,
        sample_id=cohort_id,
        caller="combine_gvcfs",
        variant_type="gvcf",
        build=ref.build,
        source_samples=sample_ids,
        source_cids=[g.cid for g in gvcfs],
    )

    # GATK writes the GVCF's index alongside it without being asked.
    idx_path = output_dir / f"{output_gvcf.name}.idx"
    if idx_path.exists():
        await VariantsIndex.store(
            idx_path, sample_id=cohort_id, companion_of=combined_vcf.cid
        )

    return combined_vcf
