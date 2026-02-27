"""
Tests for Variants type.
"""

import shutil

import pytest
from conftest import FIXTURES_DIR

from stargazer.types import Variants
from stargazer.types.variants import VariantsFile, VariantsIndex
from stargazer.utils.storage import default_client


@pytest.mark.asyncio
async def test_variants_fetch():
    """Test fetch() downloads VCF and index files to cache."""
    vcf_fixture = FIXTURES_DIR / "dummy.vcf"
    tbi_fixture = FIXTURES_DIR / "dummy.vcf.tbi"

    vcf_fixture.write_text(
        "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    )
    tbi_fixture.write_text("dummy_index")

    try:
        test_cid_vcf = "QmTestVcf"
        test_cid_tbi = "QmTestTbi"
        default_client.local_dir.mkdir(parents=True, exist_ok=True)
        cached_vcf = default_client.local_dir / test_cid_vcf
        cached_tbi = default_client.local_dir / test_cid_tbi
        shutil.copy(vcf_fixture, cached_vcf)
        shutil.copy(tbi_fixture, cached_tbi)

        vcf = VariantsFile(
            cid=test_cid_vcf,
            keyvalues={
                "type": "variants",
                "component": "vcf",
                "sample_id": "NA12829",
                "caller": "deepvariant",
            },
        )
        tbi = VariantsIndex(
            cid=test_cid_tbi,
            keyvalues={
                "type": "variants",
                "component": "index",
                "sample_id": "NA12829",
            },
        )

        variants = Variants(sample_id="NA12829", vcf=vcf, index=tbi)

        cache_dir = await variants.fetch()

        assert cache_dir == default_client.local_dir
        assert cache_dir.exists()
        assert variants.vcf.path is not None
        assert variants.vcf.path.exists()
        assert variants.index.path is not None
        assert variants.index.path.exists()
    finally:
        if vcf_fixture.exists():
            vcf_fixture.unlink()
        if tbi_fixture.exists():
            tbi_fixture.unlink()


@pytest.mark.asyncio
async def test_variants_get_vcf_path():
    """Test direct access to vcf component returns correct path."""
    vcf_fixture = FIXTURES_DIR / "dummy2.vcf"
    vcf_fixture.write_text("##fileformat=VCFv4.2\n")

    try:
        test_cid_vcf = "QmTestVcfGetPath"
        default_client.local_dir.mkdir(parents=True, exist_ok=True)
        cached_vcf = default_client.local_dir / test_cid_vcf
        shutil.copy(vcf_fixture, cached_vcf)

        vcf = VariantsFile(
            cid=test_cid_vcf,
            path=cached_vcf,
            keyvalues={"type": "variants", "component": "vcf", "sample_id": "NA12829"},
        )

        variants = Variants(sample_id="NA12829", vcf=vcf)

        vcf_path = variants.vcf.path
        assert vcf_path == cached_vcf
        assert vcf_path.exists()
    finally:
        if vcf_fixture.exists():
            vcf_fixture.unlink()


@pytest.mark.asyncio
async def test_variants_get_index_path():
    """Test direct access to index component returns correct path when present."""
    vcf_fixture = FIXTURES_DIR / "dummy3.vcf"
    tbi_fixture = FIXTURES_DIR / "dummy3.vcf.tbi"
    vcf_fixture.write_text("##fileformat=VCFv4.2\n")
    tbi_fixture.write_text("dummy_index")

    try:
        test_cid_vcf = "QmTestVcfGetIndex"
        test_cid_tbi = "QmTestTbiGetIndex"
        default_client.local_dir.mkdir(parents=True, exist_ok=True)
        cached_vcf = default_client.local_dir / test_cid_vcf
        cached_tbi = default_client.local_dir / test_cid_tbi
        shutil.copy(vcf_fixture, cached_vcf)
        shutil.copy(tbi_fixture, cached_tbi)

        vcf = VariantsFile(
            cid=test_cid_vcf,
            path=cached_vcf,
            keyvalues={"type": "variants", "component": "vcf"},
        )
        tbi = VariantsIndex(
            cid=test_cid_tbi,
            path=cached_tbi,
            keyvalues={"type": "variants", "component": "index"},
        )

        variants = Variants(sample_id="NA12829", vcf=vcf, index=tbi)

        index_path = variants.index.path
        assert index_path == cached_tbi
        assert index_path.exists()
    finally:
        if vcf_fixture.exists():
            vcf_fixture.unlink()
        if tbi_fixture.exists():
            tbi_fixture.unlink()


@pytest.mark.asyncio
async def test_variants_get_index_path_none():
    """Test index component is None when index not present."""
    vcf_fixture = FIXTURES_DIR / "dummy4.vcf"
    vcf_fixture.write_text("##fileformat=VCFv4.2\n")

    try:
        test_cid_vcf = "QmTestVcfNoIndex"
        default_client.local_dir.mkdir(parents=True, exist_ok=True)
        cached_vcf = default_client.local_dir / test_cid_vcf
        shutil.copy(vcf_fixture, cached_vcf)

        vcf = VariantsFile(
            cid=test_cid_vcf,
            path=cached_vcf,
            keyvalues={"type": "variants", "component": "vcf"},
        )

        variants = Variants(sample_id="NA12829", vcf=vcf)
        assert variants.index is None
    finally:
        if vcf_fixture.exists():
            vcf_fixture.unlink()


@pytest.mark.asyncio
async def test_variants_update_components():
    """Test component update() uploads files and sets metadata."""
    vcf_fixture = FIXTURES_DIR / "dummy5.vcf"
    tbi_fixture = FIXTURES_DIR / "dummy5.vcf.tbi"
    vcf_fixture.write_text("##fileformat=VCFv4.2\n")
    tbi_fixture.write_text("dummy_index")

    try:
        vcf = VariantsFile()
        await vcf.update(
            vcf_fixture,
            sample_id="NA12829",
            caller="deepvariant",
            variant_type="vcf",
            build="GRCh38",
        )

        tbi = VariantsIndex()
        await tbi.update(tbi_fixture, sample_id="NA12829")

        variants = Variants(sample_id="NA12829", vcf=vcf, index=tbi)

        assert variants.vcf is not None
        assert variants.vcf.keyvalues.get("type") == "variants"
        assert variants.vcf.keyvalues.get("component") == "vcf"
        assert variants.vcf.keyvalues.get("sample_id") == "NA12829"
        assert variants.vcf.keyvalues.get("caller") == "deepvariant"
        assert variants.vcf.keyvalues.get("variant_type") == "vcf"
        assert variants.vcf.keyvalues.get("build") == "GRCh38"
        assert variants.vcf.cid != ""

        assert variants.index is not None
        assert variants.index.keyvalues.get("type") == "variants"
        assert variants.index.keyvalues.get("component") == "index"
        assert variants.index.keyvalues.get("sample_id") == "NA12829"
        assert variants.index.cid != ""
    finally:
        if vcf_fixture.exists():
            vcf_fixture.unlink()
        if tbi_fixture.exists():
            tbi_fixture.unlink()


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
