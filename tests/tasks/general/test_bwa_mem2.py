"""
Tests for BWA-MEM2 tasks.
"""

import gzip
import subprocess
from pathlib import Path

import pytest
from conftest import GENERAL_FIXTURES_DIR

from stargazer.assets import R1, R2, Alignment, Reference
from stargazer.tasks.general.bwa_mem2 import bwa_mem2_index, bwa_mem2_mem


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


@pytest.mark.asyncio
async def test_bwa_mem2_index():
    """bwa-mem2 index writes its five index files, stored as assets."""
    ref = Reference(path=GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")

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


async def test_bwa_mem2_mem_aligns_against_a_stored_index():
    """bwa_mem2_mem aligns stored mates against a reference indexed in the store."""
    ref = Reference()
    await ref.update(GENERAL_FIXTURES_DIR / "GRCh38_TP53.fa", build="GRCh38")
    await bwa_mem2_index(ref)
    r1 = R1()
    await r1.update(
        GENERAL_FIXTURES_DIR / "NA12829_TP53_R1.fq.gz", sample_id="NA12829_TP53"
    )
    r2 = R2()
    await r2.update(
        GENERAL_FIXTURES_DIR / "NA12829_TP53_R2.fq.gz", sample_id="NA12829_TP53"
    )

    bam = await bwa_mem2_mem(ref=ref, r1=r1, r2=r2)

    assert isinstance(bam, Alignment)
    assert ref.cid != ""
    assert r1.cid != ""
    assert bam.reference_cid == ref.cid
    assert bam.r1_cid == r1.cid
    assert bam.sample_id == "NA12829_TP53"
    assert primary_reads(await bam.fetch()) == 2 * fastq_reads(
        GENERAL_FIXTURES_DIR / "NA12829_TP53_R1.fq.gz"
    )
