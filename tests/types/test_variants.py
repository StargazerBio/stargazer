"""
Tests for Variants type.
"""

import pytest
from conftest import FIXTURES_DIR

from stargazer.types import Variants
from stargazer.types.variants import VariantsFile, VariantsIndex
import stargazer.utils.storage as _storage_mod


@pytest.mark.asyncio
async def test_variants_fetch(fixtures_db):
    """Test fetch() resolves VCF and index paths from CIDs via TinyDB."""
    [vcf_r] = await _storage_mod.default_client.query(
        {"type": "variants", "component": "vcf", "sample_id": "NA12829"}
    )
    [idx_r] = await _storage_mod.default_client.query(
        {"type": "variants", "component": "index", "sample_id": "NA12829"}
    )

    # No path set — fetch() must resolve via TinyDB
    vcf = VariantsFile(cid=vcf_r.cid, keyvalues=vcf_r.keyvalues)
    tbi = VariantsIndex(cid=idx_r.cid, keyvalues=idx_r.keyvalues)

    variants = Variants(sample_id="NA12829", vcf=vcf, index=tbi)
    cache_dir = await variants.fetch()

    assert cache_dir == _storage_mod.default_client.local_dir
    assert cache_dir.exists()
    assert variants.vcf.path is not None
    assert variants.vcf.path.exists()
    assert variants.index.path is not None
    assert variants.index.path.exists()


@pytest.mark.asyncio
async def test_variants_get_vcf_path():
    """Test direct access to vcf component returns correct path."""
    vcf_path = FIXTURES_DIR / "NA12829_TP53.g.vcf"
    assert vcf_path.exists()

    vcf = VariantsFile(
        cid="test",
        path=vcf_path,
        keyvalues={"type": "variants", "component": "vcf", "sample_id": "NA12829"},
    )

    variants = Variants(sample_id="NA12829", vcf=vcf)

    assert variants.vcf.path == vcf_path
    assert variants.vcf.path.exists()


@pytest.mark.asyncio
async def test_variants_get_index_path():
    """Test direct access to index component returns correct path when present."""
    vcf_path = FIXTURES_DIR / "NA12829_TP53.g.vcf"
    idx_path = FIXTURES_DIR / "NA12829_TP53.g.vcf.idx"
    assert vcf_path.exists()
    assert idx_path.exists()

    vcf = VariantsFile(
        cid="test",
        path=vcf_path,
        keyvalues={"type": "variants", "component": "vcf"},
    )
    tbi = VariantsIndex(
        cid="test",
        path=idx_path,
        keyvalues={"type": "variants", "component": "index"},
    )

    variants = Variants(sample_id="NA12829", vcf=vcf, index=tbi)

    assert variants.index.path == idx_path
    assert variants.index.path.exists()


@pytest.mark.asyncio
async def test_variants_get_index_path_none():
    """Test index component is None when index not present."""
    vcf = VariantsFile(
        cid="test",
        path=FIXTURES_DIR / "NA12829_TP53.g.vcf",
        keyvalues={"type": "variants", "component": "vcf"},
    )

    variants = Variants(sample_id="NA12829", vcf=vcf)
    assert variants.index is None


@pytest.mark.asyncio
async def test_variants_update_components():
    """Test component update() uploads files and sets metadata."""
    vcf_fixture = FIXTURES_DIR / "NA12829_TP53.g.vcf"
    idx_fixture = FIXTURES_DIR / "NA12829_TP53.g.vcf.idx"
    assert vcf_fixture.exists()
    assert idx_fixture.exists()

    vcf = VariantsFile()
    await vcf.update(
        vcf_fixture,
        sample_id="NA12829",
        caller="haplotypecaller",
        variant_type="gvcf",
        build="GRCh38",
    )

    tbi = VariantsIndex()
    await tbi.update(idx_fixture, sample_id="NA12829")

    variants = Variants(sample_id="NA12829", vcf=vcf, index=tbi)

    assert variants.vcf is not None
    assert variants.vcf.keyvalues.get("type") == "variants"
    assert variants.vcf.keyvalues.get("component") == "vcf"
    assert variants.vcf.keyvalues.get("sample_id") == "NA12829"
    assert variants.vcf.keyvalues.get("caller") == "haplotypecaller"
    assert variants.vcf.keyvalues.get("variant_type") == "gvcf"
    assert variants.vcf.keyvalues.get("build") == "GRCh38"
    assert variants.vcf.cid != ""

    assert variants.index is not None
    assert variants.index.keyvalues.get("type") == "variants"
    assert variants.index.keyvalues.get("component") == "index"
    assert variants.index.keyvalues.get("sample_id") == "NA12829"
    assert variants.index.cid != ""


@pytest.mark.asyncio
async def test_variants_fetch_empty():
    """Test fetch() raises ValueError for empty variants."""
    variants = Variants(sample_id="NA12829")

    with pytest.raises(ValueError, match="No files to fetch"):
        await variants.fetch()


@pytest.mark.asyncio
async def test_variants_get_vcf_path_not_found():
    """Test that vcf is None when component not set."""
    variants = Variants(sample_id="NA12829")
    assert variants.vcf is None


@pytest.mark.asyncio
async def test_variants_get_vcf_path_not_cached():
    """Test that path is None when file not fetched yet."""
    vcf = VariantsFile(cid="QmTest", keyvalues={"type": "variants", "component": "vcf"})
    variants = Variants(sample_id="NA12829", vcf=vcf)
    assert variants.vcf.path is None


@pytest.mark.asyncio
async def test_variants_properties():
    """Test VariantsFile properties read from keyvalues."""
    vcf = VariantsFile(keyvalues={"caller": "deepvariant", "variant_type": "gvcf"})
    variants = Variants(sample_id="NA12829", vcf=vcf)

    assert variants.vcf.caller == "deepvariant"
    assert variants.vcf.variant_type == "gvcf"

    vcf2 = VariantsFile(keyvalues={"caller": "haplotypecaller", "variant_type": "vcf"})
    variants2 = Variants(sample_id="NA12829", vcf=vcf2)

    assert variants2.vcf.caller == "haplotypecaller"
    assert variants2.vcf.variant_type == "vcf"

    vcf3 = VariantsFile()
    variants3 = Variants(sample_id="NA12829", vcf=vcf3)

    assert variants3.vcf.caller is None
    assert variants3.vcf.variant_type is None


@pytest.mark.asyncio
async def test_variants_source_samples():
    """Test source_samples property on VariantsFile."""
    vcf = VariantsFile(
        keyvalues={"sample_count": "3", "source_samples": "NA12829,NA12830,NA12831"}
    )
    variants = Variants(sample_id="NA12829", vcf=vcf)

    assert variants.vcf.sample_count == 3
    assert variants.vcf.source_samples == ["NA12829", "NA12830", "NA12831"]

    vcf2 = VariantsFile(keyvalues={"sample_count": "1"})
    variants2 = Variants(sample_id="NA12829", vcf=vcf2)

    assert variants2.vcf.sample_count == 1
    assert variants2.vcf.source_samples is None


@pytest.mark.asyncio
async def test_variants_source_samples_default():
    """Test source_samples is None when metadata not set."""
    vcf = VariantsFile()
    variants = Variants(sample_id="NA12829", vcf=vcf)
    assert variants.vcf.source_samples is None
