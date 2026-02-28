"""
Tests for base_recalibrator task.
"""

import shutil
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.base_recalibrator import base_recalibrator
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
        "known_sites": (
            "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf",
            "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf",
        ),
        "known_sites_idx": (
            "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf.idx",
            "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf.idx",
        ),
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
    Register known sites VCF in the local DB so query() can find it.
    Copies both the VCF and its index, preserving filenames for GATK compatibility.
    """
    vcf_name = "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf"
    # Copy VCF and index to local_dir preserving names
    for key in ("known_sites", "known_sites_idx"):
        src = paths[key]
        dst = local_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)

    # Insert DB record so query() finds it by keyvalues
    default_client.db.insert(
        {
            "cid": "test_known_sites",
            "keyvalues": {
                "type": "known_sites",
                "name": vcf_name,
            },
            "created_at": "2026-01-01T00:00:00+00:00",
            "rel_path": vcf_name,
        }
    )


@pytest.mark.asyncio
async def test_base_recalibrator_creates_report():
    """Test that base_recalibrator creates a recalibration report."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_bqsr"
    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir)
    register_known_sites_in_db(local_dir, paths)

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

    alignment = Alignment(
        sample_id=sample_id,
        alignment=bam_file,
    )

    ref = Reference(
        build="GRCh38",
        fasta=ref_fasta,
    )

    recal_report = await base_recalibrator(
        alignment=alignment,
        ref=ref,
        known_sites=["Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf"],
    )

    # Verify result
    assert isinstance(recal_report, ComponentFile)
    assert recal_report.keyvalues.get("type") == "bqsr_report"
    assert recal_report.keyvalues.get("sample_id") == sample_id


@pytest.mark.asyncio
async def test_base_recalibrator_rejects_empty_known_sites():
    """Test that base_recalibrator raises error for empty known_sites."""
    alignment = Alignment(sample_id="test")

    ref = Reference(build="test")

    with pytest.raises(ValueError, match="known_sites list cannot be empty"):
        await base_recalibrator(
            alignment=alignment,
            ref=ref,
            known_sites=[],
        )


@pytest.mark.asyncio
async def test_base_recalibrator_task_is_callable():
    """Test that base_recalibrator is a callable task."""
    assert callable(base_recalibrator)
    assert "base_recalibrator" in str(base_recalibrator)


class TestBQSRExports:
    """Test that BQSR tasks are properly exported."""

    def test_base_recalibrator_exported_from_package(self):
        """Test that base_recalibrator is accessible from stargazer.tasks."""
        from stargazer.tasks import base_recalibrator

        assert callable(base_recalibrator)
