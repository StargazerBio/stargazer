"""
Tests for create_sequence_dictionary task.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.create_sequence_dictionary import create_sequence_dictionary
from stargazer.types import Reference
from stargazer.types.reference import ReferenceFile, ReferenceIndex


@pytest.mark.asyncio
async def test_create_sequence_dictionary_creates_dict(fixtures_db):
    """Test create_sequence_dictionary creates .dict file."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    ref = Reference(
        build="GRCh38",
        fasta=ReferenceFile(
            path=FIXTURES_DIR / "GRCh38_TP53.fa",
            keyvalues={"type": "reference", "component": "fasta", "build": "GRCh38"},
        ),
        faidx=ReferenceIndex(
            path=FIXTURES_DIR / "GRCh38_TP53.fa.fai",
            keyvalues={"type": "reference", "component": "faidx", "build": "GRCh38"},
        ),
    )

    fixtures_db()  # checkout: switch to isolated work dir

    result = await create_sequence_dictionary(ref)

    assert isinstance(result, Reference)
    assert result.build == "GRCh38"
    assert result.sequence_dictionary is not None
    assert (
        result.sequence_dictionary.keyvalues.get("tool")
        == "gatk_CreateSequenceDictionary"
    )
    assert result.sequence_dictionary.keyvalues.get("type") == "reference"
    assert (
        result.sequence_dictionary.keyvalues.get("component") == "sequence_dictionary"
    )
    assert result.sequence_dictionary.keyvalues.get("build") == "GRCh38"
    assert result.sequence_dictionary.path is not None
    assert result.sequence_dictionary.path.exists()


@pytest.mark.asyncio
async def test_create_sequence_dictionary_is_callable():
    """Test that create_sequence_dictionary is a callable task."""
    assert callable(create_sequence_dictionary)
    assert "create_sequence_dictionary" in str(create_sequence_dictionary)


class TestExports:
    """Test that create_sequence_dictionary is properly exported."""

    def test_exported_from_package(self):
        """Test that create_sequence_dictionary is accessible from stargazer.tasks."""
        from stargazer.tasks import create_sequence_dictionary

        assert callable(create_sequence_dictionary)
