"""
Tests for joint_call_gvcfs task.
"""

import pytest
from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR

from stargazer.assets import Reference, Variants
from stargazer.tasks.gatk.joint_call_gvcfs import joint_call_gvcfs


@pytest.mark.tools
@pytest.mark.asyncio
async def test_joint_call_gvcfs_defaults_to_every_contig(fixtures_db):
    """With no intervals, joint calling covers every contig in the reference."""
    gvcf = Variants(
        path=GATK_FIXTURES_DIR / "NA12829_TP53.g.vcf",
        sample_id="NA12829",
        caller="haplotypecaller",
        variant_type="gvcf",
        build="GRCh38",
    )
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")

    fixtures_db()  # checkout: switch to isolated work dir

    result = await joint_call_gvcfs(gvcfs=[gvcf], ref=ref, cohort_id="cohort")

    lines = (await result.fetch()).read_text().splitlines()
    header = next(line for line in lines if line.startswith("#CHROM"))
    records = [line.split("\t") for line in lines if not line.startswith("#")]
    assert header.split("\t")[9:] == ["NA12829"]
    assert {r[0] for r in records} == {"chr17:7658421-7697490"}
