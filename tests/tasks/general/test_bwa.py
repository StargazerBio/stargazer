"""
Tests for BWA tasks.
"""

import gzip
import subprocess
from pathlib import Path

import pytest
from conftest import GENERAL_FIXTURES_DIR

from stargazer.assets import R1, R2, AlignerIndex, Alignment, Reference, assemble
from stargazer.tasks.general.bwa import bwa_index, bwa_mem


def primary_reads(bam: Path) -> int:
    """Count the BAM's records, leaving out secondary and supplementary alignments."""
    out = subprocess.run(
        ["samtools", "view", "-c", "-F", "0x900", str(bam)],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(out.stdout)


def fastq_reads(fastq: Path) -> int:
    """Count the reads in a gzipped FASTQ."""
    with gzip.open(fastq, "rt") as f:
        return sum(1 for _ in f) // 4


def header_lines(bam: Path) -> list[str]:
    """Return the lines of the BAM's header."""
    out = subprocess.run(
        ["samtools", "view", "-H", str(bam)],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.splitlines()


@pytest.mark.asyncio
async def test_bwa_index():
    """Test bwa index creates all index files (.amb, .ann, .bwt, .pac, .sa)."""
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")

    result = await bwa_index(ref)

    assert isinstance(result, list)
    assert len(result) == 5, "Should have exactly 5 BWA index files"

    index_extensions = [".amb", ".ann", ".bwt", ".pac", ".sa"]
    for ext in index_extensions:
        matching = [idx for idx in result if idx.path and idx.path.name.endswith(ext)]
        assert len(matching) == 1, f"Should have exactly one {ext} file"

        idx = matching[0]
        assert isinstance(idx, AlignerIndex)
        assert idx.aligner == "bwa"
        assert idx.build == "GRCh38"
        assert idx.path is not None
        assert (await idx.fetch()).exists()


@pytest.mark.asyncio
async def test_bwa_index_missing_file():
    """Test that bwa_index raises error when reference file is missing."""
    ref = Reference(path=Path("/nonexistent/path/ref.fasta"), build="GRCh38")

    with pytest.raises((FileNotFoundError, RuntimeError)):
        await bwa_index(ref)


async def test_bwa_mem_aligns_paired_reads():
    """bwa_mem aligns both mates with a read group and stores one alignment."""
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")
    r1 = R1(
        path=GENERAL_FIXTURES_DIR / "NA12829_TP53_R1.fq.gz", sample_id="NA12829_TP53"
    )
    r2 = R2(
        path=GENERAL_FIXTURES_DIR / "NA12829_TP53_R2.fq.gz", sample_id="NA12829_TP53"
    )

    bam = await bwa_mem(ref=ref, r1=r1, r2=r2)

    assert isinstance(bam, Alignment)
    assert bam.sample_id == "NA12829_TP53"
    assert bam.duplicates_marked is False
    assert bam.bqsr_applied is False

    bam_path = await bam.fetch()
    assert primary_reads(bam_path) == 2 * fastq_reads(
        GENERAL_FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    )

    header = header_lines(bam_path)
    assert "@RG\tID:NA12829_TP53\tSM:NA12829_TP53\tLB:lib\tPL:ILLUMINA" in header

    (stored,) = await assemble(asset="alignment", sample_id="NA12829_TP53")
    assert stored.cid == bam.cid
