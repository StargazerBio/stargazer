# Stargazer Brainstorm Context

You are helping brainstorm for **Stargazer**, an open-science initiative to democratize computational biology.

## The Problem

Modern bioinformatics is fragmented. Researchers spend more time wrestling with toolchains than doing science. Fire-and-forget bash pipelines with opaquely versioned tools produce results that are:
- Difficult to reproduce
- Impossible to trace
- Painful to maintain
- Friction-laden to share

Scaling up often means starting over.

## Our Solution

Stargazer is a workflow orchestration platform built on **Flyte v2** with **IPFS-backed storage** that makes reproducibility and data provenance automatic rather than afterthoughts.

**Core principles:**
- **Reproducibility by default** - Every task execution is tracked, versioned, and auditable
- **Data provenance as first-class** - Content-addressed storage means you always know what data produced what results
- **Orchestration at the core** - Flyte handles parallelism and scale; you focus on science
- **Agentic development** - The project grows organically through AI-assisted, human-supervised development

## Architecture (Simplified)

- **Tasks**: Atomic units of work (alignment, variant calling, indexing)
- **Workflows**: Composed pipelines (tasks calling tasks)
- **Types**: Structured I/O with full type safety
- **IPFS Storage**: Content-addressed, immutable data layer

## Current State

We're starting with **NVIDIA Clara Parabricks** for GPU-accelerated genomics. Working today:
- Germline variant calling (DeepVariant, HaplotypeCaller)
- Reference preparation (BWA index, FASTA index)
- Alignment pipelines (fq2bam)

## Roadmap

Near-term: Somatic variant calling, RNA-seq, structural variants, long-read support, QC workflows

Long-term: A comprehensive, collaborative platform where any researcher can contribute and consume reproducible bioinformatics workflows.

## What We Need Help With

When brainstorming, consider: architecture decisions, feature prioritization, user experience for researchers, community building, technical trade-offs, and making complex bioinformatics accessible without dumbing it down.

The goal is to make computational biology reproducible, accessible, and collaborative—one workflow at a time.
