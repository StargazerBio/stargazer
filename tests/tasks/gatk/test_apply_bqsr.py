"""
Tests for apply_bqsr task.
"""

import pytest
from conftest import GATK_FIXTURES_DIR, GENERAL_FIXTURES_DIR

from stargazer.assets import (
    Alignment,
    AlignmentIndex,
    BQSRReport,
    Reference,
    assemble,
)
from stargazer.tasks.gatk.apply_bqsr import apply_bqsr


@pytest.mark.asyncio
async def test_apply_bqsr_recalibrates_bam():
    """Test that apply_bqsr creates a recalibrated BAM."""
    sample_id = "NA12829_TP53_markdup"

    alignment = Alignment(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_markdup.bam",
        sample_id=sample_id,
        sorted="coordinate",
        duplicates_marked=True,
        tool="gatk_mark_duplicates",
    )

    ref = Reference(
        path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa",
        build="GRCh38",
    )

    bqsr_report = BQSRReport(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_bqsr.table",
        sample_id=sample_id,
        tool="gatk_base_recalibrator",
    )

    recalibrated = await apply_bqsr(
        alignment=alignment,
        ref=ref,
        bqsr_report=bqsr_report,
    )

    assert isinstance(recalibrated, Alignment)
    assert recalibrated.sample_id == sample_id
    assert recalibrated.bqsr_applied is True
    assert recalibrated.tool == "gatk_apply_bqsr"
    assert recalibrated.path is not None
    assert (await recalibrated.fetch()).exists()

    (index,) = await assemble(asset="alignment_index", companion_of=recalibrated.cid)
    assert index.sample_id == sample_id
    assert index.path.name == "NA12829_TP53_markdup_recalibrated.bai"


async def test_apply_bqsr_links_its_output_to_its_input():
    """The recalibrated BAM records the BAM it was made from."""
    sample_id = "NA12829_TP53_markdup"

    alignment = Alignment()
    await alignment.update(
        GATK_FIXTURES_DIR / "NA12829_TP53_markdup.bam",
        sample_id=sample_id,
        sorted="coordinate",
        duplicates_marked=True,
        tool="gatk_mark_duplicates",
    )
    await AlignmentIndex().update(
        GATK_FIXTURES_DIR / "NA12829_TP53_markdup.bai",
        sample_id=sample_id,
        companion_of=alignment.cid,
    )

    ref = Reference(
        path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa",
        build="GRCh38",
    )

    bqsr_report = BQSRReport(
        path=GATK_FIXTURES_DIR / "NA12829_TP53_bqsr.table",
        sample_id=sample_id,
        tool="gatk_base_recalibrator",
    )

    recalibrated = await apply_bqsr(
        alignment=alignment,
        ref=ref,
        bqsr_report=bqsr_report,
    )

    assert alignment.cid != ""
    assert recalibrated.source_cid == alignment.cid
    found = await assemble(asset="alignment", source_cid=alignment.cid)
    assert [a.cid for a in found] == [recalibrated.cid]
