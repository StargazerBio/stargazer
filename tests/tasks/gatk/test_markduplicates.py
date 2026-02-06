"""
Tests for markduplicates task.
"""

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from stargazer.tasks.gatk.markduplicates import markduplicates
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
async def test_markduplicates_marks_duplicates():
    """Test that markduplicates creates a marked BAM."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_markdup"
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
            "tool": "gatk_mergebamalignment",
            "sorted": "coordinate",
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

    marked = await markduplicates(
        alignment=alignment,
        ref=ref,
    )

    # Verify result
    assert isinstance(marked, Alignment)
    assert marked.sample_id == sample_id

    # Check metadata
    bam_file = marked.alignment
    assert bam_file is not None
    assert bam_file.keyvalues.get("duplicates_marked") == "true"
    assert bam_file.keyvalues.get("tool") == "gatk_markduplicates"


@pytest.mark.asyncio
async def test_markduplicates_task_is_callable():
    """Test that markduplicates is a callable task."""
    assert callable(markduplicates)
    assert "markduplicates" in str(markduplicates)


class TestMarkDuplicatesExports:
    """Test that markduplicates task is properly exported."""

    def test_markduplicates_exported_from_package(self):
        """Test that markduplicates is accessible from stargazer.tasks."""
        from stargazer.tasks import markduplicates

        assert callable(markduplicates)
