"""
Stargazer MCP Server.

Exposes all storage, task, and workflow capabilities as MCP tools,
resources, and prompts via FastMCP. Supports stdio and Streamable HTTP
transports.

Usage:
    stargazer              # stdio transport (default)
    stargazer --http       # streamable-http transport
"""

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from stargazer.utils.pinata import IpFile, default_client
from stargazer.types import Reference, Alignment, Reads, Variants

# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------

mcp = FastMCP("stargazer")

# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_result(obj) -> dict | list | str:
    """Serialize any stargazer type to JSON-friendly structure."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    elif isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, list):
        return [_serialize_result(item) for item in obj]
    elif isinstance(obj, tuple):
        return [_serialize_result(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _serialize_result(v) for k, v in obj.items()}
    else:
        return str(obj)


# ---------------------------------------------------------------------------
# Storage tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def query_files(keyvalues: dict[str, str]) -> list[dict]:
    """Query files by metadata key-value pairs. Returns matching files."""
    files = await default_client.query_files(keyvalues)
    return [f.to_dict() for f in files]


@mcp.tool()
async def upload_file(path: str, keyvalues: dict[str, str]) -> dict:
    """Upload a file with metadata key-value pairs."""
    ipfile = await default_client.upload_file(Path(path), keyvalues=keyvalues)
    return ipfile.to_dict()


@mcp.tool()
async def download_file(file_id: str) -> str:
    """Download a file by ID to local cache. Returns the local path."""
    # Query for the file by ID to reconstruct the IpFile
    from tinydb import Query

    File = Query()
    record = default_client.db.get(File.id == file_id)
    if record:
        ipfile = default_client._ipfile_from_db_record(record)
    else:
        # Try treating file_id as a CID for non-local files
        from datetime import datetime, timezone

        ipfile = IpFile(
            id=file_id,
            cid=file_id,
            name=None,
            size=0,
            keyvalues={},
            created_at=datetime.now(timezone.utc),
        )
    ipfile = await default_client.download_file(ipfile)
    return str(ipfile.local_path)


@mcp.tool()
async def delete_file(file_id: str) -> str:
    """Delete a file by ID."""
    from tinydb import Query

    File = Query()
    record = default_client.db.get(File.id == file_id)
    if record:
        ipfile = default_client._ipfile_from_db_record(record)
        await default_client.delete_file(ipfile)
        return f"Deleted file {file_id}"
    else:
        return f"File {file_id} not found"


# ---------------------------------------------------------------------------
# Bioinformatics task tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def hydrate(filters: dict[str, str | list[str]]) -> list[dict]:
    """Hydrate types from storage based on key-value filters.

    Queries storage and reconstructs typed objects (Reference, Alignment,
    Reads, Variants) from their component files. Uses cartesian product
    for list-valued filters.
    """
    from stargazer.tasks import hydrate as _hydrate

    results = await _hydrate(filters)
    return [_serialize_result(r) for r in results]


@mcp.tool()
async def bwa_index(ref: dict) -> dict:
    """Create BWA index files for a reference genome.

    Takes a serialized Reference dict and returns an updated Reference
    with BWA index files (.amb, .ann, .bwt, .pac, .sa) added.
    """
    from stargazer.tasks import bwa_index as _bwa_index

    reference = Reference.from_dict(ref)
    result = await _bwa_index(reference)
    return result.to_dict()


@mcp.tool()
async def bwa_mem(
    reads: dict, ref: dict, read_group: dict[str, str] | None = None
) -> dict:
    """Align FASTQ reads to a reference genome using BWA-MEM.

    Takes serialized Reads and Reference dicts. Returns an Alignment dict
    with the unsorted BAM file.
    """
    from stargazer.tasks import bwa_mem as _bwa_mem

    reads_obj = Reads.from_dict(reads)
    ref_obj = Reference.from_dict(ref)
    result = await _bwa_mem(reads=reads_obj, ref=ref_obj, read_group=read_group)
    return result.to_dict()


@mcp.tool()
async def samtools_faidx(ref: dict) -> dict:
    """Create a FASTA index (.fai) using samtools faidx.

    Takes a serialized Reference dict and returns an updated Reference
    with the .fai index added.
    """
    from stargazer.tasks import samtools_faidx as _samtools_faidx

    reference = Reference.from_dict(ref)
    result = await _samtools_faidx(reference)
    return result.to_dict()


@mcp.tool()
async def sort_sam(
    alignment: dict,
    ref: dict,
    sort_order: str = "coordinate",
) -> dict:
    """Sort a SAM/BAM file using GATK SortSam.

    Takes serialized Alignment and Reference dicts. sort_order can be
    'coordinate', 'queryname', or 'duplicate'.
    """
    from stargazer.tasks import sort_sam as _sort_sam

    aln = Alignment.from_dict(alignment)
    ref_obj = Reference.from_dict(ref)
    result = await _sort_sam(alignment=aln, ref=ref_obj, sort_order=sort_order)
    return result.to_dict()


@mcp.tool()
async def mark_duplicates(alignment: dict, ref: dict) -> dict:
    """Mark duplicate reads in a BAM file using GATK MarkDuplicates.

    Takes serialized Alignment and Reference dicts. Returns an updated
    Alignment with duplicates marked.
    """
    from stargazer.tasks import mark_duplicates as _mark_duplicates

    aln = Alignment.from_dict(alignment)
    ref_obj = Reference.from_dict(ref)
    result = await _mark_duplicates(alignment=aln, ref=ref_obj)
    return result.to_dict()


@mcp.tool()
async def base_recalibrator(
    alignment: dict,
    ref: dict,
    known_sites: list[str],
) -> dict:
    """Generate a BQSR recalibration report using GATK BaseRecalibrator.

    Takes serialized Alignment and Reference dicts plus a list of known
    variant site filenames. Returns a serialized IpFile of the report.
    """
    from stargazer.tasks import base_recalibrator as _base_recalibrator

    aln = Alignment.from_dict(alignment)
    ref_obj = Reference.from_dict(ref)
    result = await _base_recalibrator(
        alignment=aln, ref=ref_obj, known_sites=known_sites
    )
    return result.to_dict()


@mcp.tool()
async def apply_bqsr(alignment: dict, ref: dict, recal_report: dict) -> dict:
    """Apply BQSR recalibration to a BAM file using GATK ApplyBQSR.

    Takes serialized Alignment, Reference, and IpFile (recal report) dicts.
    Returns an updated Alignment with recalibrated quality scores.
    """
    from stargazer.tasks import apply_bqsr as _apply_bqsr

    aln = Alignment.from_dict(alignment)
    ref_obj = Reference.from_dict(ref)
    report = IpFile.from_dict(recal_report)
    result = await _apply_bqsr(alignment=aln, ref=ref_obj, recal_report=report)
    return result.to_dict()


@mcp.tool()
async def create_sequence_dictionary(ref: dict) -> dict:
    """Create a sequence dictionary (.dict) using GATK CreateSequenceDictionary.

    Takes a serialized Reference dict and returns an updated Reference
    with the .dict file added.
    """
    from stargazer.tasks import (
        create_sequence_dictionary as _create_sequence_dictionary,
    )

    reference = Reference.from_dict(ref)
    result = await _create_sequence_dictionary(reference)
    return result.to_dict()


@mcp.tool()
async def genotype_gvcf(gvcf: dict, ref: dict) -> dict:
    """Convert GVCF to VCF using GATK GenotypeGVCFs (joint genotyping).

    Takes serialized Variants (GVCF) and Reference dicts. Returns a
    Variants dict with the final VCF.
    """
    from stargazer.tasks import genotype_gvcf as _genotype_gvcf

    gvcf_obj = Variants.from_dict(gvcf)
    ref_obj = Reference.from_dict(ref)
    result = await _genotype_gvcf(gvcf=gvcf_obj, ref=ref_obj)
    return result.to_dict()


@mcp.tool()
async def combine_gvcfs(
    gvcfs: list[dict],
    ref: dict,
    cohort_id: str = "cohort",
) -> dict:
    """Combine multiple per-sample GVCFs into a single multi-sample GVCF.

    Uses GATK CombineGVCFs. Takes a list of serialized Variants dicts
    and a Reference dict. Returns a combined Variants dict.
    """
    from stargazer.tasks import combine_gvcfs as _combine_gvcfs

    gvcf_objs = [Variants.from_dict(g) for g in gvcfs]
    ref_obj = Reference.from_dict(ref)
    result = await _combine_gvcfs(gvcfs=gvcf_objs, ref=ref_obj, cohort_id=cohort_id)
    return result.to_dict()


@mcp.tool()
async def genomics_db_import(
    gvcfs: list[dict],
    workspace_path: str,
    intervals: list[str] | None = None,
    batch_size: int = 50,
) -> str:
    """Import GVCFs to GenomicsDB for scalable joint genotyping.

    Takes a list of serialized Variants dicts and a workspace path.
    Returns the path to the created GenomicsDB workspace.
    """
    from stargazer.tasks import genomics_db_import as _genomics_db_import

    gvcf_objs = [Variants.from_dict(g) for g in gvcfs]
    result = await _genomics_db_import(
        gvcfs=gvcf_objs,
        workspace_path=Path(workspace_path),
        intervals=intervals,
        batch_size=batch_size,
    )
    return str(result)


@mcp.tool()
async def variant_recalibrator(
    vcf: dict,
    ref: dict,
    resources: list[dict],
    annotations: list[str],
    mode: str = "SNP",
    tranches: list[float] | None = None,
    max_gaussians: int = 8,
) -> dict:
    """Build a VQSR recalibration model using GATK VariantRecalibrator.

    Takes serialized Variants and Reference dicts plus VQSR resource configs.
    Each resource dict needs: name, vcf_name, known, training, truth, prior.
    Returns dict with recal_file and tranches_file paths.
    """
    from stargazer.tasks import variant_recalibrator as _variant_recalibrator
    from stargazer.tasks import VQSRResource

    vcf_obj = Variants.from_dict(vcf)
    ref_obj = Reference.from_dict(ref)
    resource_objs = [
        VQSRResource(
            name=r["name"],
            vcf_name=r["vcf_name"],
            known=r["known"],
            training=r["training"],
            truth=r["truth"],
            prior=r["prior"],
        )
        for r in resources
    ]
    recal_file, tranches_file = await _variant_recalibrator(
        vcf=vcf_obj,
        ref=ref_obj,
        resources=resource_objs,
        annotations=annotations,
        mode=mode,
        tranches=tranches,
        max_gaussians=max_gaussians,
    )
    return {"recal_file": str(recal_file), "tranches_file": str(tranches_file)}


@mcp.tool()
async def apply_vqsr(
    vcf: dict,
    recal_file: str,
    tranches_file: str,
    ref: dict | None = None,
    mode: str = "SNP",
    truth_sensitivity_filter_level: float = 99.0,
) -> dict:
    """Apply VQSR filtering using GATK ApplyVQSR.

    Takes serialized Variants dict and paths to recal/tranches files.
    Returns a filtered Variants dict.
    """
    from stargazer.tasks import apply_vqsr as _apply_vqsr

    vcf_obj = Variants.from_dict(vcf)
    ref_obj = Reference.from_dict(ref) if ref else None
    result = await _apply_vqsr(
        vcf=vcf_obj,
        recal_file=Path(recal_file),
        tranches_file=Path(tranches_file),
        ref=ref_obj,
        mode=mode,
        truth_sensitivity_filter_level=truth_sensitivity_filter_level,
    )
    return result.to_dict()


# ---------------------------------------------------------------------------
# Composite workflow tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def prepare_reference(ref_name: str) -> dict:
    """Prepare a reference genome with all required indices.

    Hydrates reference from storage, then creates FASTA index,
    sequence dictionary, and BWA index. Returns a fully-indexed
    Reference dict.
    """
    from stargazer.workflows.gatk_data_preprocessing import (
        prepare_reference as _prepare_reference,
    )

    result = await _prepare_reference(ref_name=ref_name)
    return result.to_dict()


@mcp.tool()
async def preprocess_sample(
    sample_id: str,
    ref: dict,
    known_sites: list[str] | None = None,
    run_bqsr: bool = True,
) -> dict:
    """Pre-process a single sample for variant calling.

    Aligns reads with BWA-MEM, sorts, marks duplicates, and optionally
    applies BQSR. Takes a serialized Reference dict. Returns an
    Alignment dict ready for variant calling.
    """
    from stargazer.workflows.gatk_data_preprocessing import (
        preprocess_sample as _preprocess_sample,
    )

    ref_obj = Reference.from_dict(ref)
    result = await _preprocess_sample(
        sample_id=sample_id,
        ref=ref_obj,
        known_sites=known_sites,
        run_bqsr=run_bqsr,
    )
    return result.to_dict()


@mcp.tool()
async def preprocess_cohort(
    sample_ids: list[str],
    ref_name: str,
    known_sites: list[str] | None = None,
    run_bqsr: bool = True,
) -> list[dict]:
    """Pre-process multiple samples in parallel for variant calling.

    Prepares reference, then processes each sample: align, sort, mark
    duplicates, optional BQSR. Returns list of Alignment dicts.
    """
    from stargazer.workflows.gatk_data_preprocessing import (
        preprocess_cohort as _preprocess_cohort,
    )

    results = await _preprocess_cohort(
        sample_ids=sample_ids,
        ref_name=ref_name,
        known_sites=known_sites,
        run_bqsr=run_bqsr,
    )
    return [a.to_dict() for a in results]


@mcp.tool()
async def germline_single_sample(
    sample_id: str,
    ref_name: str,
    known_sites: list[str] | None = None,
    run_bqsr: bool = False,
) -> dict:
    """Single-sample germline short variant discovery workflow.

    Prepares reference, pre-processes reads, calls variants with
    HaplotypeCaller, and genotypes. Returns dict with alignment and vcf.
    """
    from stargazer.workflows.germline_short_variant_discovery import (
        germline_single_sample as _germline_single_sample,
    )

    alignment, vcf = await _germline_single_sample(
        sample_id=sample_id,
        ref_name=ref_name,
        known_sites=known_sites,
        run_bqsr=run_bqsr,
    )
    return {
        "alignment": alignment.to_dict(),
        "vcf": vcf.to_dict(),
    }


@mcp.tool()
async def germline_cohort(
    sample_ids: list[str],
    ref_name: str,
    cohort_id: str = "cohort",
    known_sites: list[str] | None = None,
    run_bqsr: bool = False,
) -> dict:
    """Multi-sample (cohort) germline short variant discovery workflow.

    Processes each sample in parallel, consolidates GVCFs with
    CombineGVCFs, then joint genotypes. Returns dict with alignments,
    gvcfs, and joint_vcf.
    """
    from stargazer.workflows.germline_short_variant_discovery import (
        germline_cohort as _germline_cohort,
    )

    alignments, gvcfs, joint_vcf = await _germline_cohort(
        sample_ids=sample_ids,
        ref_name=ref_name,
        cohort_id=cohort_id,
        known_sites=known_sites,
        run_bqsr=run_bqsr,
    )
    return {
        "alignments": [a.to_dict() for a in alignments],
        "gvcfs": [g.to_dict() for g in gvcfs],
        "joint_vcf": joint_vcf.to_dict(),
    }


@mcp.tool()
async def germline_cohort_with_vqsr(
    sample_ids: list[str],
    ref_name: str,
    cohort_id: str = "cohort",
    known_sites: list[str] | None = None,
    run_bqsr: bool = False,
    vqsr_snp_resources: list[dict] | None = None,
    vqsr_indel_resources: list[dict] | None = None,
    snp_truth_sensitivity: float = 99.0,
    indel_truth_sensitivity: float = 99.0,
) -> dict:
    """Complete germline workflow with VQSR filtering.

    Runs the full cohort germline pipeline including VQSR for
    production-quality variant calls. Returns dict with alignments,
    gvcfs, joint_vcf, and filtered_vcf.
    """
    from stargazer.workflows.germline_short_variant_discovery import (
        germline_cohort_with_vqsr as _germline_cohort_with_vqsr,
    )
    from stargazer.tasks import VQSRResource

    snp_res = None
    if vqsr_snp_resources:
        snp_res = [
            VQSRResource(
                name=r["name"],
                vcf_name=r["vcf_name"],
                known=r["known"],
                training=r["training"],
                truth=r["truth"],
                prior=r["prior"],
            )
            for r in vqsr_snp_resources
        ]

    indel_res = None
    if vqsr_indel_resources:
        indel_res = [
            VQSRResource(
                name=r["name"],
                vcf_name=r["vcf_name"],
                known=r["known"],
                training=r["training"],
                truth=r["truth"],
                prior=r["prior"],
            )
            for r in vqsr_indel_resources
        ]

    alignments, gvcfs, joint_vcf, filtered_vcf = await _germline_cohort_with_vqsr(
        sample_ids=sample_ids,
        ref_name=ref_name,
        cohort_id=cohort_id,
        known_sites=known_sites,
        run_bqsr=run_bqsr,
        vqsr_snp_resources=snp_res,
        vqsr_indel_resources=indel_res,
        snp_truth_sensitivity=snp_truth_sensitivity,
        indel_truth_sensitivity=indel_truth_sensitivity,
    )
    return {
        "alignments": [a.to_dict() for a in alignments],
        "gvcfs": [g.to_dict() for g in gvcfs],
        "joint_vcf": joint_vcf.to_dict(),
        "filtered_vcf": filtered_vcf.to_dict(),
    }


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("stargazer://references")
async def list_references() -> str:
    """List available reference genomes with their components."""
    refs = await default_client.query_files({"type": "reference"})
    # Group by build
    builds: dict[str, list[dict]] = {}
    for f in refs:
        build = f.keyvalues.get("build", "unknown")
        builds.setdefault(build, []).append(
            {
                "component": f.keyvalues.get("component", "unknown"),
                "name": f.name,
                "id": f.id,
            }
        )
    return json.dumps(builds, indent=2)


@mcp.resource("stargazer://samples")
async def list_samples() -> str:
    """List available samples and their data types."""
    # Query reads and alignments
    reads = await default_client.query_files({"type": "reads"})
    alignments = await default_client.query_files({"type": "alignment"})
    variants = await default_client.query_files({"type": "variants"})

    samples: dict[str, dict[str, list[str]]] = {}
    for f in reads:
        sid = f.keyvalues.get("sample_id", "unknown")
        samples.setdefault(sid, {"reads": [], "alignments": [], "variants": []})
        comp = f.keyvalues.get("component", "unknown")
        samples[sid]["reads"].append(comp)
    for f in alignments:
        sid = f.keyvalues.get("sample_id", "unknown")
        samples.setdefault(sid, {"reads": [], "alignments": [], "variants": []})
        comp = f.keyvalues.get("component", "unknown")
        samples[sid]["alignments"].append(comp)
    for f in variants:
        sid = f.keyvalues.get("sample_id", "unknown")
        samples.setdefault(sid, {"reads": [], "alignments": [], "variants": []})
        comp = f.keyvalues.get("component", "unknown")
        samples[sid]["variants"].append(comp)

    return json.dumps(samples, indent=2)


@mcp.resource("stargazer://workflows")
async def list_workflows() -> str:
    """List available workflows with parameter descriptions."""
    workflows = {
        "prepare_reference": {
            "description": "Prepare reference genome with all indices",
            "parameters": {"ref_name": "Reference genome name (e.g. GRCh38.fa)"},
        },
        "preprocess_sample": {
            "description": "Pre-process a single sample (align, sort, mark dups, optional BQSR)",
            "parameters": {
                "sample_id": "Sample identifier",
                "ref": "Prepared Reference (serialized dict)",
                "known_sites": "List of known variant VCF filenames for BQSR",
                "run_bqsr": "Whether to apply BQSR (default: True)",
            },
        },
        "preprocess_cohort": {
            "description": "Pre-process multiple samples in parallel",
            "parameters": {
                "sample_ids": "List of sample identifiers",
                "ref_name": "Reference genome name",
                "known_sites": "Known variant VCF filenames for BQSR",
                "run_bqsr": "Whether to apply BQSR (default: True)",
            },
        },
        "germline_single_sample": {
            "description": "Single-sample germline variant discovery",
            "parameters": {
                "sample_id": "Sample identifier",
                "ref_name": "Reference genome name",
                "known_sites": "Known variant VCF filenames for BQSR",
                "run_bqsr": "Whether to apply BQSR (default: False)",
            },
        },
        "germline_cohort": {
            "description": "Multi-sample germline variant discovery with joint calling",
            "parameters": {
                "sample_ids": "List of sample identifiers",
                "ref_name": "Reference genome name",
                "cohort_id": "Cohort identifier (default: 'cohort')",
                "known_sites": "Known variant VCF filenames for BQSR",
                "run_bqsr": "Whether to apply BQSR (default: False)",
            },
        },
        "germline_cohort_with_vqsr": {
            "description": "Complete germline workflow with VQSR filtering",
            "parameters": {
                "sample_ids": "List of sample identifiers",
                "ref_name": "Reference genome name",
                "cohort_id": "Cohort identifier",
                "known_sites": "Known variant VCF filenames for BQSR",
                "run_bqsr": "Whether to apply BQSR",
                "vqsr_snp_resources": "VQSR resources for SNP recalibration",
                "vqsr_indel_resources": "VQSR resources for INDEL recalibration",
            },
        },
    }
    return json.dumps(workflows, indent=2)


@mcp.resource("stargazer://runs")
async def list_runs() -> str:
    """List recent workflow runs with status.

    Note: Run tracking requires Flyte backend. In local mode,
    this returns an empty list.
    """
    # In local mode we do not have a Flyte backend to query
    return json.dumps({"runs": [], "note": "Run tracking requires Flyte backend."})


@mcp.resource("stargazer://config")
async def show_config() -> str:
    """Show current Stargazer mode and configuration."""
    config = {
        "local_only": default_client.local_only,
        "local_dir": str(default_client.local_dir),
        "public": default_client.public,
        "gateway": default_client.gateway,
        "has_jwt": default_client._jwt is not None,
        "stargazer_mode": os.environ.get("STARGAZER_MODE", "local"),
    }
    return json.dumps(config, indent=2)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt()
def align_reads(sample_id: str, ref_build: str) -> str:
    """Generate instructions for aligning reads to a reference genome."""
    return (
        f"Align reads for sample {sample_id} against reference build {ref_build}. "
        f"Steps:\n"
        f'1. Hydrate the reference: hydrate({{"type": "reference", "build": "{ref_build}"}})\n'
        f'2. Hydrate the reads: hydrate({{"type": "reads", "sample_id": "{sample_id}"}})\n'
        f"3. Run bwa_mem with the reads and reference.\n"
        f"4. Return the resulting alignment."
    )


@mcp.prompt()
def preprocess_sample_prompt(
    sample_id: str,
    ref_build: str,
    known_sites: str = "",
) -> str:
    """Generate instructions for full sample preprocessing."""
    steps = (
        f"Pre-process sample {sample_id} against reference {ref_build}.\n"
        f"Steps:\n"
        f'1. Prepare reference with prepare_reference(ref_name="{ref_build}").\n'
        f"2. Align reads with bwa_mem.\n"
        f"3. Sort the BAM with sort_sam (coordinate order).\n"
        f"4. Mark duplicates with mark_duplicates.\n"
    )
    if known_sites:
        sites = [s.strip() for s in known_sites.split(",")]
        sites_str = json.dumps(sites)
        steps += (
            f"5. Run base_recalibrator with known_sites={sites_str}.\n"
            f"6. Apply BQSR with apply_bqsr.\n"
        )
    steps += "Return the final preprocessed Alignment."
    return steps


@mcp.prompt()
def call_variants(sample_id: str, ref_build: str) -> str:
    """Generate instructions for germline variant calling on a single sample."""
    return (
        f"Call germline variants for sample {sample_id} using reference {ref_build}.\n"
        f"Steps:\n"
        f'1. Use germline_single_sample(sample_id="{sample_id}", '
        f'ref_name="{ref_build}") to run the full pipeline.\n'
        f"2. This will prepare the reference, align reads, call variants "
        f"with HaplotypeCaller in GVCF mode, and genotype.\n"
        f"3. Return the alignment and final VCF."
    )


@mcp.prompt()
def joint_genotype(
    sample_ids: str,
    ref_build: str,
    cohort_id: str = "cohort",
) -> str:
    """Generate instructions for joint genotyping across a cohort."""
    ids = [s.strip() for s in sample_ids.split(",")]
    ids_str = json.dumps(ids)
    return (
        f"Perform joint genotyping for cohort '{cohort_id}' with samples "
        f"{ids_str} using reference {ref_build}.\n"
        f"Steps:\n"
        f"1. Use germline_cohort(sample_ids={ids_str}, "
        f'ref_name="{ref_build}", cohort_id="{cohort_id}").\n'
        f"2. This processes each sample in parallel: align, sort, mark "
        f"duplicates, call variants.\n"
        f"3. GVCFs are consolidated with CombineGVCFs.\n"
        f"4. Joint genotyping is performed with GenotypeGVCFs.\n"
        f"5. Return the joint-called VCF."
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    """Run the Stargazer MCP server."""
    import sys

    transport = "stdio"
    if "--http" in sys.argv:
        transport = "streamable-http"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
