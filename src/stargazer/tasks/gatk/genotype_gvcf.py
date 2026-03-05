"""
GenotypeGVCF task for Stargazer.

Performs joint genotyping by converting GVCF to VCF using GATK GenotypeGVCFs.
"""

import stargazer.utils.storage as _storage
from stargazer.config import gatk_env
from stargazer.types import Reference, Variants, VariantsIndex
from stargazer.types.constellation import assemble
from stargazer.utils import _run


@gatk_env.task
async def genotype_gvcf(
    gvcf: Variants,
    ref: Reference,
) -> Variants:
    """
    Convert GVCF to VCF using GATK GenotypeGVCFs (joint genotyping).

    Args:
        gvcf: Variants asset containing a GVCF file
        ref: Reference FASTA asset

    Returns:
        Variants asset with final VCF variant calls

    Reference:
        https://gatk.broadinstitute.org/hc/en-us/articles/360037057852-GenotypeGVCFs
    """
    if gvcf.variant_type != "gvcf":
        raise ValueError(
            f"genotype_gvcf requires a GVCF file, but got variant_type={gvcf.variant_type!r}. "
            f"sample_id={gvcf.sample_id}"
        )

    await _storage.default_client.download(gvcf)
    await _storage.default_client.download(ref)

    # Download reference companions (.fai, .dict) — GATK requires them alongside FASTA
    c_ref = await assemble(
        reference_cid=ref.cid, asset=["reference_index", "sequence_dict"]
    )
    if c_ref._assets:
        await c_ref.fetch()

    # Download variants index (.idx) — GATK requires it alongside GVCF
    c_vidx = await assemble(variants_cid=gvcf.cid, asset="variants_index")
    if c_vidx._assets:
        await c_vidx.fetch()

    ref_path = ref.path
    gvcf_path = gvcf.path
    output_dir = _storage.default_client.local_dir
    output_vcf = output_dir / f"{gvcf.sample_id}_genotyped.vcf"

    cmd = [
        "gatk",
        "GenotypeGVCFs",
        "-R",
        str(ref_path),
        "-V",
        str(gvcf_path),
        "-O",
        str(output_vcf),
    ]

    stdout, stderr = await _run(cmd, cwd=str(output_dir))

    if not output_vcf.exists():
        raise FileNotFoundError(
            f"GenotypeGVCFs did not create output VCF at {output_vcf}. stderr: {stderr}"
        )

    source_samples = gvcf.source_samples or [gvcf.sample_id]
    vcf = Variants()
    await vcf.update(
        output_vcf,
        sample_id=gvcf.sample_id,
        caller="genotype_gvcf",
        variant_type="vcf",
        build=ref.build,
        sample_count=len(source_samples),
        source_samples=source_samples,
    )

    # Upload implicit index file produced by GATK
    idx_path = output_dir / f"{output_vcf.name}.idx"
    if idx_path.exists():
        vidx = VariantsIndex()
        await vidx.update(idx_path, sample_id=gvcf.sample_id, variants_cid=vcf.cid)

    return vcf
