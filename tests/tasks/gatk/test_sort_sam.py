"""
Tests for sort_sam task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.sort_sam import sort_sam
from stargazer.types import Reference, Alignment
from stargazer.utils.storage import default_client
from stargazer.utils.ipfile import IpFile


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
        "bam": ("NA12829_TP53_merged.bam", "NA12829_TP53_merged.bam"),
    }

    paths = {}
    for key, (src_name, dst_name) in files.items():
        src = FIXTURES_DIR / src_name
        dst = local_dir / dst_name
        shutil.copy2(src, dst)
        paths[key] = dst

    return paths


@pytest.mark.asyncio
async def test_sort_sam_sorts_bam():
    """Test that sort_sam creates a sorted BAM."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_sort"
    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir)

    bam_ipfile = IpFile(
        id="test-merged-bam",
        cid="test_merged_bam",
        name="NA12829_TP53_merged.bam",
        size=paths["bam"].stat().st_size,
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": sample_id,
            "tool": "bwa_mem",
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

    sorted_bam = await sort_sam(
        alignment=alignment,
        ref=ref,
        sort_order="coordinate",
    )

    # Verify result
    assert isinstance(sorted_bam, Alignment)
    assert sorted_bam.sample_id == sample_id

    # Check metadata
    bam_file = sorted_bam.alignment
    assert bam_file is not None
    assert bam_file.keyvalues.get("sorted") == "coordinate"
    assert bam_file.keyvalues.get("tool") == "gatk_sort_sam"


@pytest.mark.asyncio
async def test_sort_sam_validates_sort_order():
    """Test that sort_sam rejects invalid sort orders."""
    alignment = Alignment(
        sample_id="test",
    )

    ref = Reference(
        build="test",
    )

    with pytest.raises(ValueError, match="Invalid sort_order"):
        await sort_sam(
            alignment=alignment,
            ref=ref,
            sort_order="invalid_order",
        )


@pytest.mark.asyncio
async def test_sort_sam_task_is_callable():
    """Test that sort_sam is a callable task."""
    assert callable(sort_sam)
    assert "sort_sam" in str(sort_sam)


class TestSortSamExports:
    """Test that sort_sam task is properly exported."""

    def test_sort_sam_exported_from_package(self):
        """Test that sort_sam is accessible from stargazer.tasks."""
        from stargazer.tasks import sort_sam

        assert callable(sort_sam)
