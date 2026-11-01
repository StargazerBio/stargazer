---
sources:
  - src/stargazer/config.py
---

# Parabricks

NVIDIA Parabricks: GPU-accelerated versions of alignment, preprocessing and variant-calling tools, run as `pbrun <tool>` in NVIDIA's container. **No Stargazer task wraps it and no Stargazer image carries it**; its docs are captured as the reference for a GPU path alongside [[gatk]]. Each page is NVIDIA's documentation for the tool, quick start and options included, rather than `--help` output.

## Alignment

- [[parabricks-fq2bam]]: an accelerated BWA-MEM from FASTQ pairs to a sorted, duplicate-marked BAM or CRAM (`--no-markdups` skips marking), with an optional BQSR report
- [[parabricks-fq2bam_meth]]: the same for bisulfite-sequencing reads
- [[parabricks-rna_fq2bam]]: RNA-seq alignment
- [[parabricks-minimap2]]: long-read alignment
- [[parabricks-bam2fq]]: BAM back to FASTQ, for realigning to another reference

## Preprocessing

- [[parabricks-bamsort]]: sort by coordinate or read name
- [[parabricks-markdup]]: mark duplicate reads
- [[parabricks-bqsr]]: the base quality recalibration report
- [[parabricks-applybqsr]]: apply that report to a BAM

## Metrics

- [[parabricks-bammetrics]]: an accelerated GATK CollectWGSMetrics
- [[parabricks-collectmultiplemetrics]]: an accelerated GATK CollectMultipleMetrics

## Germline calling

- [[parabricks-haplotypecaller]]: an accelerated GATK HaplotypeCaller. Its opening paragraph is NVIDIA's CollectMultipleMetrics text, copied in their docs; the rest of the page is HaplotypeCaller's
- [[parabricks-deepvariant]]: Google's deep-learning germline caller
- [[parabricks-pangenome_aware_deepvariant]]: DeepVariant against a pangenome graph
- [[parabricks-genotypegvcf]]: an accelerated GATK GenotypeGVCFs
- [[parabricks-indexgvcf]]: index a gVCF
- [[parabricks-dbsnp]]: annotate a VCF from dbSNP
- [[parabricks-deepvariant_germline]], [[parabricks-pacbio_germline]], [[parabricks-ont_germline]]: whole pipelines from reads to variants

## Somatic calling

- [[parabricks-mutectcaller]]: an accelerated GATK Mutect2, tumor with an optional normal
- [[parabricks-deepsomatic]]: DeepVariant's somatic counterpart, tumor and normal
- [[parabricks-prepon]], [[parabricks-postpon]]: index a panel-of-normals (PON) file for mutectcaller's `--pon`, then annotate its calls against it

## RNA fusions

- [[parabricks-starfusion]]: fusion calling with STAR-Fusion

## Related

- [[gatk]]: the CPU tools Stargazer's tasks wrap
- [[tool-help]]: how tool docs are captured
