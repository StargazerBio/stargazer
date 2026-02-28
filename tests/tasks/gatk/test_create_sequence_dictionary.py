"""
Tests for create_sequence_dictionary task.
"""

import shutil
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from stargazer.tasks.gatk.create_sequence_dictionary import create_sequence_dictionary
from stargazer.types import Reference
from stargazer.types.reference import ReferenceFile, ReferenceIndex
from stargazer.utils.storage import default_client


def setup_fixture_files(local_dir: Path) -> dict[str, Path]:
    """
    Copy reference fixture files into the test's local directory.

    Returns dict of fixture name to local path.
    """
    local_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "ref_fasta": ("GRCh38_TP53.fa", "GRCh38_TP53.fa"),
        "ref_fai": ("GRCh38_TP53.fa.fai", "GRCh38_TP53.fa.fai"),
    }

    paths = {}
    for key, (src_name, dst_name) in files.items():
        src = FIXTURES_DIR / src_name
        dst = local_dir / dst_name
        shutil.copy2(src, dst)
        paths[key] = dst

    return paths


@pytest.mark.asyncio
async def test_create_sequence_dictionary_creates_dict():
    """Test create_sequence_dictionary creates .dict file."""
    if shutil.which("gatk") is None:
        pytest.skip("gatk not available in environment")

    local_dir = default_client.local_dir
    paths = setup_fixture_files(local_dir)

    ref_fasta = ReferenceFile(
        cid="test_ref_fasta_dict",
        path=paths["ref_fasta"],
        keyvalues={
            "type": "reference",
            "component": "fasta",
            "build": "GRCh38",
        },
    )

    fai_file = ReferenceIndex(
        cid="test_ref_fai_dict",
        path=paths["ref_fai"],
        keyvalues={
            "type": "reference",
            "component": "faidx",
            "build": "GRCh38",
        },
    )

    ref = Reference(
        build="GRCh38",
        fasta=ref_fasta,
        faidx=fai_file,
    )

    # Run create_sequence_dictionary
    result = await create_sequence_dictionary(ref)

    # Verify result
    assert isinstance(result, Reference)
    assert result.build == "GRCh38"

    # Verify .dict file was added
    assert result.sequence_dictionary is not None, (
        "Should have sequence_dictionary file"
    )

    # Verify .dict file has metadata
    assert (
        result.sequence_dictionary.keyvalues.get("tool")
        == "gatk_CreateSequenceDictionary"
    ), "Should have tool metadata"
    assert result.sequence_dictionary.keyvalues.get("type") == "reference", (
        "Should have type metadata"
    )
    assert (
        result.sequence_dictionary.keyvalues.get("component") == "sequence_dictionary"
    ), "Should have component metadata"
    assert result.sequence_dictionary.keyvalues.get("build") == "GRCh38", (
        "Should copy build metadata from reference"
    )

    # Verify .dict file exists at path
    assert result.sequence_dictionary.path is not None, "Should have path set"
    assert result.sequence_dictionary.path.exists(), (
        "Dictionary file should exist at path"
    )


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
