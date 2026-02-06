"""
Tests for applybqsr task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from stargazer.tasks.gatk.applybqsr import applybqsr
from stargazer.types import Reference, Alignment
from stargazer.utils.pinata import IpFile, default_client

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


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
async def test_applybqsr_recalibrates_bam():
    """Test that applybqsr creates a recalibrated BAM."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_applybqsr"
    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir)

    bam_ipfile = IpFile(
        id="test-markdup-bam",
        cid="test_markdup_bam",
        name="NA12829_TP53_markdup.bam",
        size=paths["bam"].stat().st_size,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": sample_id,
            "tool": "gatk_markduplicates",
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
        created_at=datetime.now(),
    )
    bam_ipfile.local_path = paths["bam"]

    ref_ipfile = IpFile(
        id="test-ref-fasta",
        cid="test_ref_fasta",
        name="GRCh38_TP53.fa",
        size=paths["ref_fasta"].stat().st_size,
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
        },
        created_at=datetime.now(),
    )
    ref_ipfile.local_path = paths["ref_fasta"]

    recal_ipfile = IpFile(
        id="test-recal-table",
        cid="test_recal_table",
        name="NA12829_TP53_bqsr.table",
        size=paths["recal_table"].stat().st_size,
        keyvalues={
            "type": "bqsr_report",
            "sample_id": sample_id,
            "tool": "gatk_baserecalibrator",
        },
        created_at=datetime.now(),
    )
    recal_ipfile.local_path = paths["recal_table"]

    alignment = Alignment(
        sample_id=sample_id,
        alignment=bam_ipfile,
    )

    ref = Reference(
        build="GRCh38",
        fasta=ref_ipfile,
    )

    recalibrated = await applybqsr(
        alignment=alignment,
        ref=ref,
        recal_report=recal_ipfile,
    )

    # Verify result
    assert isinstance(recalibrated, Alignment)
    assert recalibrated.sample_id == sample_id
    assert recalibrated.has_bqsr_applied

    # Check metadata
    bam_file = recalibrated.alignment
    assert bam_file is not None
    assert bam_file.keyvalues.get("bqsr_applied") == "true"
    assert bam_file.keyvalues.get("tool") == "gatk_applybqsr"


@pytest.mark.asyncio
async def test_applybqsr_task_is_callable():
    """Test that applybqsr is a callable task."""
    assert callable(applybqsr)
    assert "applybqsr" in str(applybqsr)


@pytest.mark.asyncio
async def test_alignment_has_bqsr_applied_property():
    """Test has_bqsr_applied property on Alignment type."""
    # Test alignment without BQSR
    non_bqsr_ipfile = IpFile(
        id="test-no-bqsr",
        cid="QmNoBQSR",
        name="no_bqsr.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "test",
            "sorted": "coordinate",
            "duplicates_marked": "true",
        },
        created_at=datetime.now(),
    )

    non_bqsr_alignment = Alignment(
        sample_id="test",
        alignment=non_bqsr_ipfile,
    )

    assert not non_bqsr_alignment.has_bqsr_applied

    # Test alignment with BQSR
    bqsr_ipfile = IpFile(
        id="test-with-bqsr",
        cid="QmWithBQSR",
        name="with_bqsr.bam",
        size=1000,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": "test",
            "sorted": "coordinate",
            "duplicates_marked": "true",
            "bqsr_applied": "true",
        },
        created_at=datetime.now(),
    )

    bqsr_alignment = Alignment(
        sample_id="test",
        alignment=bqsr_ipfile,
    )

    assert bqsr_alignment.has_bqsr_applied


class TestBQSRExports:
    """Test that BQSR tasks are properly exported."""

    def test_applybqsr_exported_from_package(self):
        """Test that applybqsr is accessible from stargazer.tasks."""
        from stargazer.tasks import applybqsr

        assert callable(applybqsr)
