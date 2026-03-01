"""
Tests for variant_recalibrator task.
"""

import pytest

from stargazer.tasks.gatk.variant_recalibrator import variant_recalibrator
from stargazer.types import Variants, Reference
from stargazer.types.variants import VariantsFile


def test_variant_recalibrator_task_is_callable():
    assert callable(variant_recalibrator)
    assert "variant_recalibrator" in str(variant_recalibrator)


@pytest.mark.asyncio
async def test_variant_recalibrator_rejects_gvcf():
    vcf = Variants(
        sample_id="test",
        vcf=VariantsFile(keyvalues={"variant_type": "gvcf"}),
    )
    with pytest.raises(ValueError, match="GVCF"):
        await variant_recalibrator(
            vcf=vcf,
            ref=Reference(build="test"),
            resources=[Variants(sample_id="r", vcf=VariantsFile())],
            annotations=["QD"],
        )


@pytest.mark.asyncio
async def test_variant_recalibrator_rejects_empty_resources():
    vcf = Variants(sample_id="test", vcf=VariantsFile())
    with pytest.raises(ValueError, match="resource"):
        await variant_recalibrator(
            vcf=vcf,
            ref=Reference(build="test"),
            resources=[],
            annotations=["QD"],
        )


@pytest.mark.asyncio
async def test_variant_recalibrator_rejects_empty_annotations():
    vcf = Variants(sample_id="test", vcf=VariantsFile())
    with pytest.raises(ValueError, match="annotation"):
        await variant_recalibrator(
            vcf=vcf,
            ref=Reference(build="test"),
            resources=[Variants(sample_id="r", vcf=VariantsFile())],
            annotations=[],
        )


@pytest.mark.asyncio
async def test_variant_recalibrator_rejects_invalid_mode():
    vcf = Variants(sample_id="test", vcf=VariantsFile())
    with pytest.raises(ValueError, match="mode"):
        await variant_recalibrator(
            vcf=vcf,
            ref=Reference(build="test"),
            resources=[Variants(sample_id="r", vcf=VariantsFile())],
            annotations=["QD"],
            mode="INVALID",
        )
