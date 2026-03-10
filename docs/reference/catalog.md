# Catalog

## Tasks

| Name | Description | Parameters |
|------|-------------|------------|
| `samtools_faidx` | Create a FASTA index (.fai file) using samtools faidx. | `ref` (Reference) |
| `create_sequence_dictionary` | Create a sequence dictionary (.dict file) using GATK CreateSequenceDictionary. | `ref` (Reference) |
| `bwa_index` | Create BWA index files for a reference genome using bwa index. | `ref` (Reference) |
| `bwa_mem` | Align FASTQ reads to reference genome using BWA-MEM. | `ref` (Reference), `r1` (R1), `r2` (R2 | NoneType), `read_group` (dict[str, str] | NoneType) |
| `sort_sam` | Sort a SAM/BAM file. | `alignment` (Alignment), `sort_order` (str) |
| `mark_duplicates` | Mark duplicate reads in a BAM file. | `alignment` (Alignment) |
| `merge_bam_alignment` | Merge alignment data from aligned BAM with data in unmapped BAM. | `aligned_bam` (Alignment), `unmapped_bam` (Alignment), `ref` (Reference) |
| `base_recalibrator` | Generate a Base Quality Score Recalibration report. | `alignment` (Alignment), `ref` (Reference), `known_sites` (list[KnownSites]) |
| `apply_bqsr` | Apply Base Quality Score Recalibration to a BAM file. | `alignment` (Alignment), `ref` (Reference), `bqsr_report` (BQSRReport) |
| `haplotype_caller` | Call germline variants in GVCF mode using GATK HaplotypeCaller. | `alignment` (Alignment), `ref` (Reference) |
| `joint_call_gvcfs` | Consolidate GVCFs into GenomicsDB and joint-genotype in a single task. | `gvcfs` (list[Variants]), `ref` (Reference), `intervals` (list[str]), `cohort_id` (str) |
| `combine_gvcfs` | Combine multiple per-sample GVCFs into a single multi-sample GVCF. | `gvcfs` (list[Variants]), `ref` (Reference), `cohort_id` (str) |
| `genomics_db_import` | Import GVCFs to GenomicsDB workspace for scalable joint genotyping. | `gvcfs` (list[Variants]), `workspace_path` (Path), `intervals` (list[str] | NoneType) |
| `variant_recalibrator` | Build a VQSR recalibration model using GATK VariantRecalibrator. | `vcf` (Variants), `ref` (Reference), `resources` (list[KnownSites]), `mode` (str) |
| `apply_vqsr` | Apply VQSR recalibration to a VCF using GATK ApplyVQSR. | `vcf` (Variants), `ref` (Reference), `vqsr_model` (VQSRModel), `truth_sensitivity_filter_level` (float | NoneType) |

## Workflows

| Name | Description | Parameters |
|------|-------------|------------|
| `prepare_reference` | Prepare reference genome for alignment and variant calling. | `build` (str) |
| `preprocess_sample` | Pre-process a single sample's reads for variant calling. | `build` (str), `sample_id` (str), `run_bqsr` (bool) |
| `germline_short_variant_discovery` | Germline short variant discovery from preprocessed BAMs. | `build` (str), `cohort_id` (str) |

## Asset Types

| Asset Key | Class | Module | Fields |
|-----------|-------|--------|--------|
| `aligner_index` | `AlignerIndex` | `types/reference.py` | `aligner`, `build`, `reference_cid` |
| `alignment` | `Alignment` | `types/alignment.py` | `bqsr_applied`, `duplicates_marked`, `format`, `r1_cid`, `reference_cid`, `sample_id`, `sorted`, `tool` |
| `alignment_index` | `AlignmentIndex` | `types/alignment.py` | `alignment_cid`, `sample_id` |
| `bqsr_report` | `BQSRReport` | `types/alignment.py` | `alignment_cid`, `sample_id`, `tool` |
| `duplicate_metrics` | `DuplicateMetrics` | `types/alignment.py` | `alignment_cid`, `sample_id`, `tool` |
| `known_sites` | `KnownSites` | `types/variants.py` | `build`, `known`, `prior`, `resource_name`, `training`, `truth`, `vqsr_mode` |
| `known_sites_index` | `KnownSitesIndex` | `types/variants.py` | `known_sites_cid` |
| `r1` | `R1` | `types/reads.py` | `mate_cid`, `sample_id`, `sequencing_platform` |
| `r2` | `R2` | `types/reads.py` | `mate_cid`, `sample_id`, `sequencing_platform` |
| `reference` | `Reference` | `types/reference.py` | `build` |
| `reference_index` | `ReferenceIndex` | `types/reference.py` | `build`, `reference_cid`, `tool` |
| `sequence_dict` | `SequenceDict` | `types/reference.py` | `build`, `reference_cid`, `tool` |
| `variants` | `Variants` | `types/variants.py` | `build`, `caller`, `sample_count`, `sample_id`, `source_samples`, `variant_type`, `vqsr_mode` |
| `variants_index` | `VariantsIndex` | `types/variants.py` | `sample_id`, `variants_cid` |
| `vqsr_model` | `VQSRModel` | `types/variants.py` | `build`, `mode`, `sample_id`, `tranches_path`, `variants_cid` |
