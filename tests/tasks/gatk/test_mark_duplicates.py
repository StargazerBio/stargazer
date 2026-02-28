"""
Tests for mark_duplicates task.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.mark_duplicates import mark_duplicates
from stargazer.types import Reference, Alignment
from stargazer.types.alignment import AlignmentFile
from stargazer.types.reference import ReferenceFile


@pytest.mark.asyncio
async def test_mark_duplicates_marks_duplicates(fixtures_db):
    """Test that mark_duplicates creates a marked BAM."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    sample_id = "NA12829_markdup"

    alignment = Alignment(
        sample_id=sample_id,
        alignment=AlignmentFile(
            path=FIXTURES_DIR / "NA12829_TP53_merged.bam",
            keyvalues={
                "type": "alignment",
                "component": "alignment",
                "sample_id": sample_id,
                "tool": "gatk_merge_bam_alignment",
                "sorted": "coordinate",
            },
        ),
    )

    ref = Reference(
        build="GRCh38",
        fasta=ReferenceFile(
            path=FIXTURES_DIR / "GRCh38_TP53.fa",
            keyvalues={"type": "reference", "component": "fasta", "build": "GRCh38"},
        ),
    )

    fixtures_db()  # checkout: switch to isolated work dir

    marked = await mark_duplicates(alignment=alignment, ref=ref)

    assert isinstance(marked, Alignment)
    assert marked.sample_id == sample_id

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
