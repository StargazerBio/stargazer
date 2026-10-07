"""Seed a storage client with the test fixtures.

Uploads every fixture file through the real storage client, with the
metadata and companion links the task tests query for. conftest's
`fixtures_db` runs it once per session into a temp store.
"""

from pathlib import Path

from stargazer.assets.alignment import (
    Alignment,
    AlignmentIndex,
    BQSRReport,
    DuplicateMetrics,
)
from stargazer.assets.asset import Asset
from stargazer.assets.reads import R1, R2
from stargazer.assets.reference import (
    AlignerIndex,
    Reference,
    ReferenceIndex,
    SequenceDict,
)
from stargazer.assets.variants import (
    KnownSites,
    KnownSitesIndex,
    Variants,
    VariantsIndex,
)
from stargazer.utils.storage import StorageClient

FIXTURES_DIR = Path(__file__).parent
GENERAL_DIR = FIXTURES_DIR / "general"
GATK_DIR = FIXTURES_DIR / "gatk"


async def seed(client: StorageClient) -> None:
    """Upload the fixtures into `client`'s store and index."""

    async def up(asset: Asset, path: Path) -> str:
        """Upload one fixture and return its CID."""
        await client.upload(asset, path)
        return asset.cid

    # ── Reference ──────────────────────────────────────────────────────────
    reference_cid = await up(Reference(build="GRCh38"), GENERAL_DIR / "GRCh38_TP53.fa")
    await up(
        ReferenceIndex(build="GRCh38", reference_cid=reference_cid),
        GENERAL_DIR / "GRCh38_TP53.fa.fai",
    )
    await up(
        SequenceDict(build="GRCh38", reference_cid=reference_cid),
        GENERAL_DIR / "GRCh38_TP53.dict",
    )
    for ext in ("amb", "ann", "bwt", "pac", "sa"):
        await up(
            AlignerIndex(build="GRCh38", aligner="bwa", reference_cid=reference_cid),
            GENERAL_DIR / f"GRCh38_TP53.fa.{ext}",
        )

    # ── Reads ───────────────────────────────────────────────────────────────
    r1_path = GENERAL_DIR / "NA12829_TP53_R1.fq.gz"
    r2_path = GENERAL_DIR / "NA12829_TP53_R2.fq.gz"
    r1 = R1(sample_id="NA12829")
    r2 = R2(sample_id="NA12829")
    r1_cid = await up(r1, r1_path)
    r2_cid = await up(r2, r2_path)
    # Back-fill mate CIDs now that both are known (a re-upload with new metadata).
    r1.mate_cid = r2_cid
    r2.mate_cid = r1_cid
    await up(r1, r1_path)
    await up(r2, r2_path)

    # ── Known sites ─────────────────────────────────────────────────────────
    mills_cid = await up(
        KnownSites(
            build="GRCh38",
            resource_name="mills",
            training="true",
            truth="true",
            prior="12",
            vqsr_mode="INDEL",
        ),
        GATK_DIR / "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf",
    )
    await up(
        KnownSitesIndex(known_sites_cid=mills_cid),
        GATK_DIR / "Mills_and_1000G_gold_standard.indels.TP53.hg38.vcf.idx",
    )

    # ── Alignments ──────────────────────────────────────────────────────────
    await up(
        Alignment(sample_id="NA12829", format="bam", r1_cid=r1_cid),
        GATK_DIR / "NA12829_TP53_unmapped.bam",
    )
    await up(
        Alignment(
            sample_id="NA12829",
            format="bam",
            tool="bwa",
            reference_cid=reference_cid,
            r1_cid=r1_cid,
        ),
        GATK_DIR / "NA12829_TP53_bwa_aligned.bam",
    )

    async def aligned(path: Path, index: Path, **fields) -> str:
        """Upload an alignment plus its index companion; return the alignment CID."""
        cid = await up(
            Alignment(
                sample_id="NA12829",
                format="bam",
                reference_cid=reference_cid,
                r1_cid=r1_cid,
                **fields,
            ),
            path,
        )
        await up(AlignmentIndex(sample_id="NA12829", alignment_cid=cid), index)
        return cid

    await aligned(
        GATK_DIR / "NA12829_TP53_merged.bam",
        GATK_DIR / "NA12829_TP53_merged.bai",
        tool="bwa",
    )
    await aligned(
        GATK_DIR / "NA12829_TP53_paired.bam",
        GATK_DIR / "NA12829_TP53_paired.bam.bai",
        tool="bwa",
    )
    await aligned(
        GATK_DIR / "NA12829_TP53_sorted_coordinate.bam",
        GATK_DIR / "NA12829_TP53_sorted_coordinate.bai",
        sorted="coordinate",
        tool="samtools",
    )
    markdup_cid = await aligned(
        GATK_DIR / "NA12829_TP53_markdup.bam",
        GATK_DIR / "NA12829_TP53_markdup.bai",
        sorted="coordinate",
        duplicates_marked=True,
        tool="gatk",
    )
    await up(
        DuplicateMetrics(sample_id="NA12829", tool="gatk", alignment_cid=markdup_cid),
        GATK_DIR / "NA12829_TP53_markdup_metrics.txt",
    )
    await aligned(
        GATK_DIR / "NA12829_TP53_recalibrated.bam",
        GATK_DIR / "NA12829_TP53_recalibrated.bai",
        sorted="coordinate",
        duplicates_marked=True,
        bqsr_applied=True,
        tool="gatk",
    )
    await up(
        BQSRReport(sample_id="NA12829", tool="gatk", alignment_cid=markdup_cid),
        GATK_DIR / "NA12829_TP53_bqsr.table",
    )

    # ── Variants (GVCFs) ────────────────────────────────────────────────────
    for sample_id in ("NA12829", "NA12891", "NA12892"):
        vcf_cid = await up(
            Variants(
                sample_id=sample_id,
                caller="haplotypecaller",
                variant_type="gvcf",
                build="GRCh38",
            ),
            GATK_DIR / f"{sample_id}_TP53.g.vcf",
        )
        idx_path = GATK_DIR / f"{sample_id}_TP53.g.vcf.idx"
        if idx_path.exists():
            await up(VariantsIndex(sample_id=sample_id, variants_cid=vcf_cid), idx_path)
