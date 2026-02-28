#!/usr/bin/env python3
"""
Build a TinyDB JSON file from the fixtures directory.

Uses LocalStorageClient.upload() to compute proper local_{md5} CIDs so the
fixtures DB stays in sync with live storage behaviour.

Run this script whenever fixtures are added or changed:
    uv run python tests/fixtures/build_local_db.py
"""

import asyncio
from pathlib import Path

from stargazer.types.component import ComponentFile
from stargazer.utils.local_storage import LocalStorageClient

FIXTURES_DIR = Path(__file__).parent

# Fixture file -> keyvalues mapping
FIXTURE_METADATA: dict[str, dict[str, str]] = {
    # Reference: GRCh38 TP53 region
    "GRCh38_TP53.fa": {
        "type": "reference",
        "component": "fasta",
        "build": "GRCh38",
    },
    "GRCh38_TP53.fa.fai": {
        "type": "reference",
        "component": "faidx",
        "build": "GRCh38",
    },
    "GRCh38_TP53.dict": {
        "type": "reference",
        "component": "sequence_dictionary",
        "build": "GRCh38",
    },
    # BWA index files
    "GRCh38_TP53.fa.amb": {
        "type": "reference",
        "component": "aligner_index",
        "aligner": "bwa",
        "build": "GRCh38",
    },
    "GRCh38_TP53.fa.ann": {
        "type": "reference",
        "component": "aligner_index",
        "aligner": "bwa",
        "build": "GRCh38",
    },
    "GRCh38_TP53.fa.bwt": {
        "type": "reference",
        "component": "aligner_index",
        "aligner": "bwa",
        "build": "GRCh38",
    },
    "GRCh38_TP53.fa.pac": {
        "type": "reference",
        "component": "aligner_index",
        "aligner": "bwa",
        "build": "GRCh38",
    },
    "GRCh38_TP53.fa.sa": {
        "type": "reference",
        "component": "aligner_index",
        "aligner": "bwa",
        "build": "GRCh38",
    },
    # Reads: NA12829
    "NA12829_TP53_R1.fq.gz": {
        "type": "reads",
        "component": "r1",
        "sample_id": "NA12829",
    },
    "NA12829_TP53_R2.fq.gz": {
        "type": "reads",
        "component": "r2",
        "sample_id": "NA12829",
    },
    # Alignments: NA12829 at various pipeline stages
    "NA12829_TP53_unmapped.bam": {
        "type": "alignment",
        "component": "alignment",
        "sample_id": "NA12829",
        "stage": "unmapped",
    },
    "NA12829_TP53_bwa_aligned.bam": {
        "type": "alignment",
        "component": "alignment",
        "sample_id": "NA12829",
        "stage": "bwa_aligned",
    },
    "NA12829_TP53_merged.bam": {
        "type": "alignment",
        "component": "alignment",
        "sample_id": "NA12829",
        "stage": "merged",
    },
    "NA12829_TP53_merged.bai": {
        "type": "alignment",
        "component": "index",
        "sample_id": "NA12829",
        "stage": "merged",
    },
    "NA12829_TP53_paired.bam": {
        "type": "alignment",
        "component": "alignment",
        "sample_id": "NA12829",
        "stage": "paired",
    },
    "NA12829_TP53_paired.bam.bai": {
        "type": "alignment",
        "component": "index",
        "sample_id": "NA12829",
        "stage": "paired",
    },
    "NA12829_TP53_sorted_coordinate.bam": {
        "type": "alignment",
        "component": "alignment",
        "sample_id": "NA12829",
        "stage": "sorted_coordinate",
        "sorted": "coordinate",
    },
    "NA12829_TP53_sorted_coordinate.bai": {
        "type": "alignment",
        "component": "index",
        "sample_id": "NA12829",
        "stage": "sorted_coordinate",
        "sorted": "coordinate",
    },
    "NA12829_TP53_markdup.bam": {
        "type": "alignment",
        "component": "alignment",
        "sample_id": "NA12829",
        "stage": "markdup",
        "sorted": "coordinate",
        "duplicates_marked": "true",
    },
    "NA12829_TP53_markdup.bai": {
        "type": "alignment",
        "component": "index",
        "sample_id": "NA12829",
        "stage": "markdup",
        "sorted": "coordinate",
        "duplicates_marked": "true",
    },
    "NA12829_TP53_markdup_metrics.txt": {
        "type": "alignment",
        "component": "markdup_metrics",
        "sample_id": "NA12829",
        "stage": "markdup",
    },
    "NA12829_TP53_recalibrated.bam": {
        "type": "alignment",
        "component": "alignment",
        "sample_id": "NA12829",
        "stage": "recalibrated",
        "sorted": "coordinate",
        "duplicates_marked": "true",
        "recalibrated": "true",
    },
    "NA12829_TP53_recalibrated.bai": {
        "type": "alignment",
        "component": "index",
        "sample_id": "NA12829",
        "stage": "recalibrated",
        "sorted": "coordinate",
        "duplicates_marked": "true",
        "recalibrated": "true",
    },
    "NA12829_TP53_bqsr.table": {
        "type": "bqsr_report",
        "sample_id": "NA12829",
    },
    # Known sites
    "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf": {
        "type": "known_sites",
        "name": "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf",
    },
    "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf.idx": {
        "type": "known_sites",
        "component": "index",
        "name": "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf.idx",
    },
    # Variants: GVCFs
    "NA12829_TP53.g.vcf": {
        "type": "variants",
        "component": "vcf",
        "sample_id": "NA12829",
        "caller": "haplotypecaller",
        "variant_type": "gvcf",
    },
    "NA12829_TP53.g.vcf.idx": {
        "type": "variants",
        "component": "index",
        "sample_id": "NA12829",
        "caller": "haplotypecaller",
    },
    "NA12891_TP53.g.vcf": {
        "type": "variants",
        "component": "vcf",
        "sample_id": "NA12891",
        "caller": "haplotypecaller",
        "variant_type": "gvcf",
    },
    "NA12892_TP53.g.vcf": {
        "type": "variants",
        "component": "vcf",
        "sample_id": "NA12892",
        "caller": "haplotypecaller",
        "variant_type": "gvcf",
    },
}


async def build_db() -> None:
    """Build the TinyDB JSON file using native LocalStorageClient.upload()."""
    db_path = FIXTURES_DIR / "stargazer_local.json"

    if db_path.exists():
        db_path.unlink()

    client = LocalStorageClient(local_dir=FIXTURES_DIR)

    added = 0
    for filename, keyvalues in FIXTURE_METADATA.items():
        filepath = FIXTURES_DIR / filename
        if not filepath.exists():
            print(f"  SKIP (missing): {filename}")
            continue

        comp = ComponentFile(path=filepath, keyvalues=keyvalues)
        await client.upload(comp)
        print(f"  added: {filename} → {comp.cid}")
        added += 1

    client.db.close()
    print(f"\nWrote {db_path} with {added} records")


if __name__ == "__main__":
    asyncio.run(build_db())
