"""
Tests for fq2bam task.
"""

import shutil
from datetime import datetime

import pytest
from config import TEST_ROOT

from stargazer.tasks.parabricks.fq2bam import fq2bam
from stargazer.types import Reference, Reads, Alignment
from stargazer.utils.pinata import IpFile


@pytest.mark.asyncio
async def test_fq2bam_basic():
    """Test fq2bam aligns FASTQ to BAM."""
    # Check if pbrun is available
    if shutil.which("pbrun") is None:
        pytest.skip("pbrun (Parabricks) not available in environment")

    # Setup: Create Reference with FASTA and indices
    # Use fixture files directly - BWA requires index files to be co-located
    # with the reference file using standard naming conventions
    ref_fixture = TEST_ROOT / "fixtures" / "GRCh38_TP53.fa"
    fai_fixture = TEST_ROOT / "fixtures" / "GRCh38_TP53.fa.fai"
    assert ref_fixture.exists(), f"Missing reference: {ref_fixture}"
    assert fai_fixture.exists(), f"Missing FAI index: {fai_fixture}"

    # Verify BWA indices exist
    bwa_exts = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    for ext in bwa_exts:
        idx_path = ref_fixture.parent / f"{ref_fixture.name}{ext}"
        assert idx_path.exists(), f"Missing BWA index: {idx_path}"

    # Create IpFile objects pointing directly to fixture files
    # This preserves the co-location of reference and index files that BWA requires
    ref_file = IpFile(
        id="test-ref-id",
        cid="QmTestRef",
        name="GRCh38_TP53.fa",
        size=ref_fixture.stat().st_size,
        keyvalues={"type": "reference", "build": "GRCh38"},
        created_at=datetime.now(),
        local_path=ref_fixture,
    )

    fai_file = IpFile(
        id="test-fai-id",
        cid="QmTestFai",
        name="GRCh38_TP53.fa.fai",
        size=fai_fixture.stat().st_size,
        keyvalues={"type": "reference", "build": "GRCh38"},
        created_at=datetime.now(),
        local_path=fai_fixture,
    )

    idx_files = []
    for i, ext in enumerate(bwa_exts):
        idx_path = ref_fixture.parent / f"{ref_fixture.name}{ext}"
        idx_file = IpFile(
            id=f"test-idx-{ext}-id",
            cid=f"QmTestIdx{i}",
            name=f"GRCh38_TP53.fa{ext}",
            size=idx_path.stat().st_size,
            keyvalues={"type": "reference", "build": "GRCh38"},
            created_at=datetime.now(),
            local_path=idx_path,
        )
        idx_files.append(idx_file)

    ref = Reference(
        ref_name="GRCh38_TP53.fa",
        files=[ref_file, fai_file] + idx_files,
    )

    # Setup: Create Reads with FASTQ files (also use fixture files directly)
    r1_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R1.fq.gz"
    r2_fixture = TEST_ROOT / "fixtures" / "NA12829_TP53_R2.fq.gz"
    assert r1_fixture.exists(), f"Missing R1: {r1_fixture}"
    assert r2_fixture.exists(), f"Missing R2: {r2_fixture}"

    r1_file = IpFile(
        id="test-r1-id",
        cid="QmTestR1",
        name="NA12829_TP53_R1.fq.gz",
        size=r1_fixture.stat().st_size,
        keyvalues={"type": "reads", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=r1_fixture,
    )

    r2_file = IpFile(
        id="test-r2-id",
        cid="QmTestR2",
        name="NA12829_TP53_R2.fq.gz",
        size=r2_fixture.stat().st_size,
        keyvalues={"type": "reads", "sample_id": "NA12829"},
        created_at=datetime.now(),
        local_path=r2_fixture,
    )

    reads = Reads(
        sample_id="NA12829",
        files=[r1_file, r2_file],
    )

    # Run fq2bam
    alignment = await fq2bam(reads=reads, ref=ref)

    # Verify result
    assert isinstance(alignment, Alignment)
    assert alignment.sample_id == "NA12829"
    assert alignment.bam_name is not None
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
