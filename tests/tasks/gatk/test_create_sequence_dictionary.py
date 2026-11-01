"""
Tests for create_sequence_dictionary task.
"""

import pytest
from conftest import GENERAL_FIXTURES_DIR

from stargazer.assets import Reference, SequenceDict
from stargazer.tasks.gatk.create_sequence_dictionary import create_sequence_dictionary


@pytest.mark.asyncio
async def test_create_sequence_dictionary_creates_dict():
    """Test create_sequence_dictionary creates .dict file."""
    ref = Reference(
        path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa",
        build="GRCh38",
    )

    result = await create_sequence_dictionary(ref)

    assert isinstance(result, SequenceDict)
    assert result.build == "GRCh38"
    assert result.tool == "gatk_CreateSequenceDictionary"
    assert result.path is not None
    assert (await result.fetch()).exists()
    assert result.path.name.endswith(".dict")
