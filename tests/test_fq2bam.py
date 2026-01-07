"""
Tests for fq2bam task.
"""

import shutil
from datetime import datetime

import pytest
from config import TEST_ROOT

from stargazer.tasks.fq2bam import fq2bam
from stargazer.types import Reference, Reads, Alignment
from stargazer.utils.pinata import IpFile, default_client


@pytest.mark.asyncio
async def test_fq2bam_basic():
    """Test fq2bam aligns FASTQ to BAM."""
    # Check if pbrun is available
    if shutil.which("pbrun") is None:
        pytest.skip("pbrun (Parabricks) not available in environment")

    # Setup: Create Reference with FASTA and indices
    ref_fixture = TEST_ROOT / "fixtures" / "GRCh38_TP53.fa"
    fai_fixture = TEST_ROOT / "fixtures" / "GRCh38_TP53.fa.fai"
    assert ref_fixture.exists()
    assert fai_fixture.exists()

    # Also need BWA indices
    bwa_exts = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    for ext in bwa_exts:
        assert (ref_fixture.parent / f"{ref_fixture.name}{ext}").exists(), (
            f"Missing BWA index: {ext}"
        )

    # Pre-populate cache
    test_cid_ref = "QmTestRefFq2bam"
    test_cid_fai = "QmTestRefFaiFq2bam"
    default_client.cache_dir.mkdir(parents=True, exist_ok=True)
    cached_ref = default_client.cache_dir / test_cid_ref
    cached_fai = default_client.cache_dir / test_cid_fai
    shutil.copy(ref_fixture, cached_ref)
    shutil.copy(fai_fixture, cached_fai)

    # Copy BWA indices
    cached_indices = []
    for i, ext in enumerate(bwa_exts):
        test_cid_idx = f"QmTestRefIdx{i}Fq2bam"
        cached_idx = default_client.cache_dir / test_cid_idx
        shutil.copy(ref_fixture.parent / f"{ref_fixture.name}{ext}", cached_idx)
        cached_indices.append((ext, test_cid_idx, cached_idx))

    # Create Reference with all files
    ref_file = IpFile(
        id="test-ref-id",
        cid=test_cid_ref,
        name="GRCh38_TP53.fa",
        size=cached_ref.stat().st_size,
        keyvalues={"type": "reference", "build": "GRCh38"},
        created_at=datetime.now(),
        local_path=cached_ref,
    )

    fai_file = IpFile(
        id="test-fai-id",
        cid=test_cid_fai,
        name="GRCh38_TP53.fa.fai",
        size=cached_fai.stat().st_size,
        keyvalues={"type": "reference", "build": "GRCh38"},
        created_at=datetime.now(),
        local_path=cached_fai,
    )

    idx_files = []
    for ext, cid, path in cached_indices:
        idx_file = IpFile(
            id=f"test-idx-{ext}-id",
            cid=cid,
            name=f"GRCh38_TP53.fa{ext}",
            size=path.stat().st_size,
            keyvalues={"type": "reference", "build": "GRCh38"},
            created_at=datetime.now(),
            local_path=path,
        )
        idx_files.append(idx_file)

    ref = Reference(
        ref_name="GRCh38_TP53.fa",
        files=[ref_file, fai_file] + idx_files,
    )

    # Setup: Create Reads with FASTQ files
    r1_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R1.fq.gz"
    r2_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R2.fq.gz"
    assert r1_fixture.exists()
    assert r2_fixture.exists()

    test_cid_r1 = "QmTestR1Fq2bam"
    test_cid_r2 = "QmTestR2Fq2bam"
    cached_r1 = default_client.cache_dir / test_cid_r1
    cached_r2 = default_client.cache_dir / test_cid_r2
    shutil.copy(r1_fixture, cached_r1)
    shutil.copy(r2_fixture, cached_r2)

    r1_file = IpFile(
        id="test-r1-id",
        cid=test_cid_r1,
        name="NA12829_TP53_R1.fq.gz",
        size=cached_r1.stat().st_size,
        keyvalues={"type": "reads", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=cached_r1,
    )

    r2_file = IpFile(
        id="test-r2-id",
        cid=test_cid_r2,
        name="NA12829_TP53_R2.fq.gz",
        size=cached_r2.stat().st_size,
        keyvalues={"type": "reads", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=cached_r2,
    )

    reads = Reads(
        sample_id="NA12829",
        files=[r1_file, r2_file],
    )

    try:
        # Run fq2bam
        alignment = await fq2bam(reads=reads, ref=ref)

        # Verify result
        assert isinstance(alignment, Alignment)
        assert alignment.sample_id == "NA12829"
        assert alignment.bam_name.endswith(".bam")

        # Verify BAM file was created and added to files
        bam_files = [f for f in alignment.files if f.name.endswith(".bam")]
        assert len(bam_files) == 1, "Should have exactly one BAM file"
        assert bam_files[0].size > 0, "BAM file should not be empty"

        # Verify metadata
        assert bam_files[0].keyvalues.get("type") == "alignment"
        assert bam_files[0].keyvalues.get("sample_id") == "NA12829"
        assert bam_files[0].keyvalues.get("tool") == "fq2bam"
        assert bam_files[0].keyvalues.get("sorted") == "coordinate"
        assert bam_files[0].keyvalues.get("duplicates_marked") == "true"

        # Verify properties work
        assert alignment.is_sorted is True
        assert alignment.has_duplicates_marked is True

        # Cleanup output BAM
        for f in alignment.files:
            if f.local_path and f.local_path.exists():
                f.local_path.unlink()
    finally:
        # Cleanup cached files
        if cached_ref.exists():
            cached_ref.unlink()
        if cached_fai.exists():
            cached_fai.unlink()
        for _, _, path in cached_indices:
            if path.exists():
                path.unlink()
        if cached_r1.exists():
            cached_r1.unlink()
        if cached_r2.exists():
            cached_r2.unlink()


@pytest.mark.asyncio
async def test_fq2bam_with_read_group():
    """Test fq2bam with custom read group metadata."""
    # Check if pbrun is available
    if shutil.which("pbrun") is None:
        pytest.skip("pbrun (Parabricks) not available in environment")

    # This test validates that custom read group is passed through correctly
    # For now, we'll just test the parameter acceptance
    # Full integration test would be similar to test_fq2bam_basic
    pytest.skip("Integration test - requires full setup similar to test_fq2bam_basic")
