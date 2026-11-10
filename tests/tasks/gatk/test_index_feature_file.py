"""
Tests for the index_feature_file task.
"""

from conftest import GATK_FIXTURES_DIR

import stargazer.utils.storage as _storage
from stargazer.assets import KnownSites
from stargazer.tasks.gatk.index_feature_file import index_feature_file


async def test_index_feature_file_stores_the_index_as_a_companion():
    """The GATK index is stored beside the VCF and listed as its companion."""
    sites = KnownSites()
    await sites.update(
        GATK_FIXTURES_DIR / "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf",
        build="GRCh38",
    )

    index = await index_feature_file(sites)

    assert index.companion_of == sites.cid
    index_path = await index.fetch()
    assert index_path.name == "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf.idx"
    assert index_path.stat().st_size > 0

    rows = await _storage.get_client().companions(sites.cid)
    assert [r["name"] for r in rows] == [
        "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf.idx"
    ]
