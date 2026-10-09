"""
Tests for BWA-MEM2 tasks.
"""

import pytest
from conftest import GENERAL_FIXTURES_DIR

from stargazer.assets import Reference
from stargazer.tasks.general.bwa_mem2 import bwa_mem2_index


@pytest.mark.tools
@pytest.mark.asyncio
async def test_bwa_mem2_index(fixtures_db):
    """bwa-mem2 index writes its five index files, stored as assets."""
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")

    fixtures_db()  # checkout: switch to isolated work dir

    result = await bwa_mem2_index(ref)

    names = sorted([(await idx.fetch()).name for idx in result])
    assert names == [
        "GRCh38_TP53.fa.0123",
        "GRCh38_TP53.fa.amb",
        "GRCh38_TP53.fa.ann",
        "GRCh38_TP53.fa.bwt.2bit.64",
        "GRCh38_TP53.fa.pac",
    ]
    assert {idx.aligner for idx in result} == {"bwa-mem2"}
