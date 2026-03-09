"""
Tests for Variants asset types.
"""

import pytest
from conftest import FIXTURES_DIR

from stargazer.types.variants import Variants, VariantsIndex, KnownSites
import stargazer.utils.storage as _storage_mod


@pytest.mark.asyncio
async def test_variants_fetch(fixtures_db):
    """Test download() resolves VCF and index paths from CIDs via TinyDB."""
    [vcf_r] = await _storage_mod.default_client.query(
        {"asset": "variants", "sample_id": "NA12829"}
    )
    [idx_r] = await _storage_mod.default_client.query(
        {"asset": "variants_index", "sample_id": "NA12829"}
    )

    # No path set — download() must resolve via TinyDB
    await _storage_mod.default_client.download(vcf_r)
    await _storage_mod.default_client.download(idx_r)

    assert vcf_r.path is not None
    assert vcf_r.path.exists()
    assert idx_r.path is not None
    assert idx_r.path.exists()


@pytest.mark.asyncio
async def test_variants_get_vcf_path():
    """Test direct access to variants asset returns correct path."""
    vcf_path = FIXTURES_DIR / "NA12829_TP53.g.vcf"
    assert vcf_path.exists()

    vcf = Variants(
        cid="test",
        path=vcf_path,
        keyvalues={"asset": "variants", "sample_id": "NA12829"},
    )

    assert vcf.path == vcf_path
    assert vcf.path.exists()


@pytest.mark.asyncio
async def test_variants_update_components():
    """Test asset update() uploads files and sets metadata."""
    vcf_fixture = FIXTURES_DIR / "NA12829_TP53.g.vcf"
    idx_fixture = FIXTURES_DIR / "NA12829_TP53.g.vcf.idx"
    assert vcf_fixture.exists()
    assert idx_fixture.exists()

    vcf = Variants()
    await vcf.update(
        vcf_fixture,
        sample_id="NA12829",
        caller="haplotypecaller",
        variant_type="gvcf",
        build="GRCh38",
    )

    tbi = VariantsIndex()
    await tbi.update(idx_fixture, sample_id="NA12829")

    assert vcf.keyvalues.get("asset") == "variants"
    assert vcf.keyvalues.get("sample_id") == "NA12829"
    assert vcf.keyvalues.get("caller") == "haplotypecaller"
    assert vcf.keyvalues.get("variant_type") == "gvcf"
    assert vcf.keyvalues.get("build") == "GRCh38"
    assert vcf.cid != ""

    assert tbi.keyvalues.get("asset") == "variants_index"
    assert tbi.keyvalues.get("sample_id") == "NA12829"
    assert tbi.cid != ""


@pytest.mark.asyncio
async def test_variants_path_not_cached():
    """Test that path is None when asset not fetched yet."""
    vcf = Variants(cid="QmTest", keyvalues={"asset": "variants"})
    assert vcf.path is None


@pytest.mark.asyncio
async def test_variants_properties():
    """Test Variants properties read from keyvalues."""
    vcf = Variants(caller="deepvariant", variant_type="gvcf")
    assert vcf.caller == "deepvariant"
    assert vcf.variant_type == "gvcf"

    vcf2 = Variants(caller="haplotypecaller", variant_type="vcf")
    assert vcf2.caller == "haplotypecaller"
    assert vcf2.variant_type == "vcf"

    vcf3 = Variants()
    assert vcf3.caller == ""
    assert vcf3.variant_type == ""


@pytest.mark.asyncio
async def test_variants_source_samples():
    """Test source_samples and sample_count properties on Variants asset."""
    vcf = Variants(sample_count=3, source_samples=["NA12829", "NA12830", "NA12831"])
    assert vcf.sample_count == 3
    assert vcf.source_samples == ["NA12829", "NA12830", "NA12831"]

    vcf2 = Variants(sample_count=1)
    assert vcf2.sample_count == 1
    assert vcf2.source_samples is None


@pytest.mark.asyncio
async def test_variants_source_samples_default():
    """Test source_samples is None when metadata not set."""
    vcf = Variants()
    assert vcf.source_samples is None


@pytest.mark.asyncio
async def test_known_sites_standalone(fixtures_db):
    """Test KnownSites is a standalone asset scoped by build."""
    results = await _storage_mod.default_client.query(
        {"asset": "known_sites", "build": "GRCh38"}
    )
    assert len(results) > 0
    for r in results:
        assert r.keyvalues.get("asset") == "known_sites"
        assert r.keyvalues.get("build") == "GRCh38"
        # No sample_id on known sites — reference-scoped
        assert "sample_id" not in r.keyvalues


@pytest.mark.asyncio
async def test_known_sites_asset():
    """Test KnownSites asset keyvalues."""
    ks = KnownSites()
    ks.build = "GRCh38"
    assert ks.keyvalues.get("asset") == "known_sites"
    assert ks.build == "GRCh38"
