#!/usr/bin/env python3
"""
Build a TinyDB JSON file from the fixtures directory.

This creates a stargazer_local.json that maps each fixture file to its
metadata keyvalues, enabling tests to use query() and hydrate() in local mode
instead of manually constructing ComponentFile objects.

Run this script whenever fixtures are added or changed:
    python tests/fixtures/build_local_db.py
"""

from datetime import datetime, timezone
from pathlib import Path

from tinydb import TinyDB

FIXTURES_DIR = Path(__file__).parent

# Fixture file -> keyvalues mapping
# Each entry maps a filename to the keyvalues dict that would be set on upload.
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
        "aligner": "bwa_index",
        "build": "GRCh38",
    },
    "GRCh38_TP53.fa.ann": {
        "type": "reference",
        "component": "aligner_index",
        "aligner": "bwa_index",
        "build": "GRCh38",
    },
    "GRCh38_TP53.fa.bwt": {
        "type": "reference",
        "component": "aligner_index",
        "aligner": "bwa_index",
        "build": "GRCh38",
    },
    "GRCh38_TP53.fa.pac": {
        "type": "reference",
        "component": "aligner_index",
        "aligner": "bwa_index",
        "build": "GRCh38",
    },
    "GRCh38_TP53.fa.sa": {
        "type": "reference",
        "component": "aligner_index",
        "aligner": "bwa_index",
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
    },
    "NA12892_TP53.g.vcf": {
        "type": "variants",
        "component": "vcf",
        "sample_id": "NA12892",
        "caller": "haplotypecaller",
    },
}


def build_db():
    """Build the TinyDB JSON file from fixture files."""
    db_path = FIXTURES_DIR / "stargazer_local.json"

    # Remove existing DB to start fresh
    if db_path.exists():
        db_path.unlink()

    db = TinyDB(db_path)
    now = datetime.now(timezone.utc).isoformat()

    for filename, keyvalues in FIXTURE_METADATA.items():
        filepath = FIXTURES_DIR / filename
        if not filepath.exists():
            print(f"  SKIP (missing): {filename}")
            continue

        record = {
            "id": f"local_{filename}",
            "cid": f"local_{filename}",
            "name": filename,
            "size": filepath.stat().st_size,
            "keyvalues": keyvalues,
            "created_at": now,
            "is_public": False,
            "rel_path": filename,
        }
        db.insert(record)
        print(f"  added: {filename}")

    db.close()
    print(f"\nWrote {db_path} with {len(FIXTURE_METADATA)} records")


if __name__ == "__main__":
    build_db()
