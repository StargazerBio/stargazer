"""
Tests for mark_duplicates task.
"""

import shutil
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.mark_duplicates import mark_duplicates
from stargazer.types import Reference, Alignment
from stargazer.types.alignment import AlignmentFile
from stargazer.types.reference import ReferenceFile
import stargazer.utils.storage as _storage_mod


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
async def test_mark_duplicates_marks_duplicates():
    """Test that mark_duplicates creates a marked BAM."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_markdup"
    local_dir = _storage_mod.default_client.local_dir
    paths = setup_fixture_files(local_dir)

    bam_file = AlignmentFile(
        cid="test_merged_bam",
        path=paths["bam"],
        keyvalues={
            "type": "alignment",
            "component": "alignment",
            "sample_id": sample_id,
            "tool": "gatk_merge_bam_alignment",
            "sorted": "coordinate",
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

    marked = await mark_duplicates(
        alignment=alignment,
        ref=ref,
    )

    # Verify result
    assert isinstance(marked, Alignment)
    assert marked.sample_id == sample_id

    # Check metadata
    result_bam = marked.alignment
    assert result_bam is not None
    assert result_bam.keyvalues.get("duplicates_marked") == "true"
    assert result_bam.keyvalues.get("tool") == "gatk_mark_duplicates"


@pytest.mark.asyncio
async def test_mark_duplicates_task_is_callable():
    """Test that mark_duplicates is a callable task."""
    assert callable(mark_duplicates)
    assert "mark_duplicates" in str(mark_duplicates)


class TestMarkDuplicatesExports:
    """Test that mark_duplicates task is properly exported."""

    def test_mark_duplicates_exported_from_package(self):
        """Test that mark_duplicates is accessible from stargazer.tasks."""
        from stargazer.tasks import mark_duplicates

        assert callable(mark_duplicates)
