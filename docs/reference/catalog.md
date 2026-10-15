# Catalog

## Tasks

| Name | Description | Parameters |
|------|-------------|------------|
| `apply_bqsr` | Apply Base Quality Score Recalibration to a BAM file. | `alignment` (`Alignment`), `ref` (`Reference`), `bqsr_report` (`BQSRReport`) |
| `apply_vqsr` | Apply VQSR recalibration to a VCF using GATK ApplyVQSR. | `vcf` (`Variants`), `ref` (`Reference`), `vqsr_model` (`VQSRModel`), `truth_sensitivity_filter_level` (`float | NoneType`) |
| `base_recalibrator` | Generate a Base Quality Score Recalibration report. | `alignment` (`Alignment`), `ref` (`Reference`), `known_sites` (`list[KnownSites]`) |
| `bwa_index` | Create BWA index files for a reference genome using bwa index. | `ref` (`Reference`) |
| `bwa_mem` | Align FASTQ reads to reference genome using BWA-MEM. | `ref` (`Reference`), `r1` (`R1`), `r2` (`R2 | NoneType`), `read_group` (`dict[str, str] | NoneType`) |
| `bwa_mem2_index` | Create BWA-MEM2 index files for a reference genome. | `ref` (`Reference`) |
| `bwa_mem2_mem` | Align FASTQ reads to reference genome using BWA-MEM2. | `ref` (`Reference`), `r1` (`R1`), `r2` (`R2 | NoneType`), `read_group` (`dict[str, str] | NoneType`) |
| `cluster` | Assign cells to clusters using the Leiden algorithm. | `adata` (`AnnData`), `resolution` (`float`), `key_added` (`str`) |
| `combine_gvcfs` | Combine multiple per-sample GVCFs into a single multi-sample GVCF. | `gvcfs` (`list[Variants]`), `ref` (`Reference`), `cohort_id` (`str`) |
| `create_sequence_dictionary` | Create a sequence dictionary (.dict file) using GATK CreateSequenceDictionary. | `ref` (`Reference`) |
| `find_markers` | Identify marker genes for each cluster using differential expression. | `adata` (`AnnData`), `groupby` (`str`), `method` (`str`) |
| `haplotype_caller` | Call germline variants in GVCF mode using GATK HaplotypeCaller. | `alignment` (`Alignment`), `ref` (`Reference`) |
| `index_feature_file` | Index a VCF file using GATK IndexFeatureFile. | `known_sites` (`KnownSites`) |
| `joint_call_gvcfs` | Consolidate GVCFs into GenomicsDB and joint-genotype in a single task. | `gvcfs` (`list[Variants]`), `ref` (`Reference`), `intervals` (`list[str] | NoneType`), `cohort_id` (`str`) |
| `mark_duplicates` | Mark duplicate reads in a BAM file. | `alignment` (`Alignment`) |
| `merge_bam_alignment` | Merge alignment data from aligned BAM with data in unmapped BAM. | `aligned_bam` (`Alignment`), `unmapped_bam` (`Alignment`), `ref` (`Reference`) |
| `normalize` | Normalize counts and apply log1p transformation. | `adata` (`AnnData`) |
| `qc_filter` | Filter low-quality cells and genes from raw scRNA-seq data. | `adata` (`AnnData`), `min_genes` (`int`), `min_cells` (`int`), `max_pct_mt` (`float`), `batch_key` (`str`), `organism` (`str`) |
| `reduce_dimensions` | Compute PCA, k-nearest neighbor graph, and UMAP embedding. | `adata` (`AnnData`), `n_pcs` (`int`), `n_neighbors` (`int`) |
| `samtools_faidx` | Create a FASTA index (.fai file) using samtools faidx. | `ref` (`Reference`) |
| `select_features` | Select highly variable genes for dimensionality reduction. | `adata` (`AnnData`), `n_top_genes` (`int`), `batch_key` (`str`) |
| `sort_sam` | Sort a SAM/BAM file. | `alignment` (`Alignment`), `sort_order` (`str`) |
| `variant_recalibrator` | Build a VQSR recalibration model using GATK VariantRecalibrator. | `vcf` (`Variants`), `ref` (`Reference`), `resources` (`list[KnownSites]`), `mode` (`str`) |

## Workflows

| Name | Description | Parameters |
|------|-------------|------------|
| `germline_short_variant_discovery` | End-to-end germline short variant discovery from raw reads. | `build` (`str`), `sample_ids` (`list[str]`), `cohort_id` (`str`) |
| `prepare_reference` | Prepare reference genome for alignment and variant calling. | `build` (`str`) |
| `preprocess_sample` | Pre-process a single sample's reads for variant calling. | `build` (`str`), `sample_id` (`str`) |
| `scrna_clustering_pipeline` | End-to-end scRNA-seq clustering pipeline. | `sample_id` (`str`), `organism` (`str`), `n_top_genes` (`int`), `resolution` (`float`), `max_pct_mt` (`float`) |

## Asset Types

| Asset Key | Class | Module | Fields |
|-----------|-------|--------|--------|
| `aligner_index` | `AlignerIndex` | `assets/reference.py` | `aligner`, `build`, `companion_of` |
| `alignment` | `Alignment` | `assets/alignment.py` | `bqsr_applied`, `duplicates_marked`, `r1_cid`, `reference_cid`, `sample_id`, `sorted`, `tool` |
| `alignment_index` | `AlignmentIndex` | `assets/alignment.py` | `companion_of`, `sample_id` |
| `anndata` | `AnnData` | `assets/scrna.py` | `n_obs`, `n_vars`, `organism`, `sample_id`, `source_cid`, `stage` |
| `bqsr_report` | `BQSRReport` | `assets/alignment.py` | `alignment_cid`, `sample_id`, `tool` |
| `duplicate_metrics` | `DuplicateMetrics` | `assets/alignment.py` | `alignment_cid`, `sample_id`, `tool` |
| `known_sites` | `KnownSites` | `assets/variants.py` | `build`, `known`, `prior`, `resource_name`, `training`, `truth`, `vqsr_mode` |
| `known_sites_index` | `KnownSitesIndex` | `assets/variants.py` | `companion_of` |
| `r1` | `R1` | `assets/reads.py` | `mate_cid`, `sample_id`, `sequencing_platform` |
| `r2` | `R2` | `assets/reads.py` | `mate_cid`, `sample_id`, `sequencing_platform` |
| `reference` | `Reference` | `assets/reference.py` | `build` |
| `reference_index` | `ReferenceIndex` | `assets/reference.py` | `build`, `companion_of`, `tool` |
| `sequence_dict` | `SequenceDict` | `assets/reference.py` | `build`, `companion_of`, `tool` |
| `variants` | `Variants` | `assets/variants.py` | `build`, `caller`, `sample_count`, `sample_id`, `source_samples`, `variant_type`, `vqsr_mode` |
| `variants_index` | `VariantsIndex` | `assets/variants.py` | `companion_of`, `sample_id` |
| `vqsr_model` | `VQSRModel` | `assets/variants.py` | `build`, `mode`, `sample_id`, `tranches_path`, `variants_cid` |

## Bundles

| Name | Description | Files |
|------|-------------|-------|
| `scrna_demo` | Human bone marrow mononuclear cells from two healthy donors (10x Multiome gene expression) for demo workflows | 2 |
| `variant_calling_demo` | TP53 region test fixtures (reference and paired reads) for GRCh38 | 3 |
