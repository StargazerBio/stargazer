"""
Tests for apply_bqsr task.
"""

import shutil
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.apply_bqsr import apply_bqsr
from stargazer.types import Reference, Alignment
from stargazer.types.alignment import AlignmentFile
from stargazer.types.component import ComponentFile
from stargazer.types.reference import ReferenceFile
from stargazer.utils.storage import default_client


def setup_fixture_files(local_dir: Path) -> dict[str, Path]:
    """
    Copy real TP53 fixture files into the test's local directory.

    Returns dict of fixture name to local path.
    """
    local_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "ref_fasta": ("GRCh38_TP53.fa", "GRCh38_TP53.fa"),
        "ref_fai": ("GRCh38_TP53.fa.fai", "GRCh38_TP53.fa.fai"),
        "ref_dict": ("GRCh38_TP53.dict", "GRCh38_TP53.dict"),
        "bam": ("NA12829_TP53_markdup.bam", "NA12829_TP53_markdup.bam"),
        "bam_bai": ("NA12829_TP53_markdup.bai", "NA12829_TP53_markdup.bai"),
        "recal_table": ("NA12829_TP53_bqsr.table", "NA12829_TP53_bqsr.table"),
    }

    paths = {}
    for key, (src_name, dst_name) in files.items():
        src = FIXTURES_DIR / src_name
        dst = local_dir / dst_name
        shutil.copy2(src, dst)
        paths[key] = dst

    return paths


@pytest.mark.asyncio
async def test_apply_bqsr_recalibrates_bam():
    """Test that apply_bqsr creates a recalibrated BAM."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_apply_bqsr"
    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir)

    bam_file = AlignmentFile(
        cid="test_markdup_bam",
        path=paths["bam"],
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": sample_id,
            "tool": "gatk_mark_duplicates",
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
    )

    ref_fasta = ReferenceFile(
        cid="test_ref_fasta",
        path=paths["ref_fasta"],
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
        },
    )

    recal_file = ComponentFile(
        cid="test_recal_table",
        path=paths["recal_table"],
        keyvalues={
            "type": "bqsr_report",
            "sample_id": sample_id,
            "tool": "gatk_baserecalibrator",
        },
    )

    alignment = Alignment(
        sample_id=sample_id,
        alignment=bam_file,
    )

    ref = Reference(
        build="GRCh38",
        fasta=ref_fasta,
    )

    recalibrated = await apply_bqsr(
        alignment=alignment,
        ref=ref,
        recal_report=recal_file,
    )

    # Verify result
    assert isinstance(recalibrated, Alignment)
    assert recalibrated.sample_id == sample_id
    assert recalibrated.has_bqsr_applied

    # Check metadata
    result_bam = recalibrated.alignment
    assert result_bam is not None
    assert result_bam.keyvalues.get("bqsr_applied") == "true"
    assert result_bam.keyvalues.get("tool") == "gatk_apply_bqsr"


@pytest.mark.asyncio
async def test_apply_bqsr_task_is_callable():
    """Test that apply_bqsr is a callable task."""
    assert callable(apply_bqsr)
    assert "apply_bqsr" in str(apply_bqsr)


@pytest.mark.asyncio
async def test_alignment_has_bqsr_applied_property():
    """Test has_bqsr_applied property on Alignment type."""
    # Test alignment without BQSR
    non_bqsr_file = AlignmentFile(
        cid="QmNoBQSR",
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "test",
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
    )

    non_bqsr_alignment = Alignment(
        sample_id="test",
        alignment=non_bqsr_file,
    )

    assert not non_bqsr_alignment.has_bqsr_applied

    # Test alignment with BQSR
    bqsr_file = AlignmentFile(
        cid="QmWithBQSR",
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "test",
            "sorted": "coordinate",
            "duplicates_marked": "true",
            "bqsr_applied": "true",
        },
    )

    bqsr_alignment = Alignment(
        sample_id="test",
        alignment=bqsr_file,
    )

    assert bqsr_alignment.has_bqsr_applied


class TestBQSRExports:
    """Test that BQSR tasks are properly exported."""

    def test_apply_bqsr_exported_from_package(self):
        """Test that apply_bqsr is accessible from stargazer.tasks."""
        from stargazer.tasks import apply_bqsr

        assert callable(apply_bqsr)
