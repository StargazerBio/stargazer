"""
Tests for baserecalibrator task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.baserecalibrator import baserecalibrator
from stargazer.types import Reference, Alignment
from stargazer.utils.pinata import IpFile, default_client


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
        "known_sites": ("known_sites_TP53.vcf", "known_sites_TP53.vcf"),
        "known_sites_idx": ("known_sites_TP53.vcf.idx", "known_sites_TP53.vcf.idx"),
    }

    paths = {}
    for key, (src_name, dst_name) in files.items():
        src = FIXTURES_DIR / src_name
        dst = local_dir / dst_name
        shutil.copy2(src, dst)
        paths[key] = dst

    return paths


def register_known_sites_in_db(local_dir: Path, paths: dict[str, Path]):
    """
    Insert known sites VCF record directly into TinyDB so query_files() can find it.
    Uses a rel_path that preserves the .vcf extension for GATK compatibility.
    """
    default_client.db.insert(
        {
            "id": "test-known-sites",
            "cid": "test_known_sites",
            "name": "known_sites_TP53.vcf",
            "size": paths["known_sites"].stat().st_size,
            "keyvalues": {
                "type": "known_sites",
                "name": "known_sites_TP53.vcf",
            },
            "created_at": datetime.now().isoformat(),
            "is_public": False,
            "rel_path": "known_sites_TP53.vcf",
        }
    )


@pytest.mark.asyncio
async def test_baserecalibrator_creates_report():
    """Test that baserecalibrator creates a recalibration report."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_bqsr"
    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir)
    register_known_sites_in_db(local_dir, paths)

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

    alignment = Alignment(
        sample_id=sample_id,
        alignment=bam_ipfile,
    )

    ref = Reference(
        build="GRCh38",
        fasta=ref_ipfile,
    )

    recal_report = await baserecalibrator(
        alignment=alignment,
        ref=ref,
        known_sites=["known_sites_TP53.vcf"],
    )

    # Verify result
    assert isinstance(recal_report, IpFile)
    assert recal_report.keyvalues.get("type") == "bqsr_report"
    assert recal_report.keyvalues.get("sample_id") == sample_id


@pytest.mark.asyncio
async def test_baserecalibrator_rejects_empty_known_sites():
    """Test that baserecalibrator raises error for empty known_sites."""
    alignment = Alignment(sample_id="test")

    ref = Reference(build="test")

    with pytest.raises(ValueError, match="known_sites list cannot be empty"):
        await baserecalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=[],
        )


@pytest.mark.asyncio
async def test_baserecalibrator_task_is_callable():
    """Test that baserecalibrator is a callable task."""
    assert callable(baserecalibrator)
    assert "baserecalibrator" in str(baserecalibrator)


class TestBQSRExports:
    """Test that BQSR tasks are properly exported."""

    def test_baserecalibrator_exported_from_package(self):
        """Test that baserecalibrator is accessible from stargazer.tasks."""
        from stargazer.tasks import baserecalibrator

        assert callable(baserecalibrator)
