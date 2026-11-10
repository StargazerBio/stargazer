---
title: provenance-on-every-output
status: doing
priority: normal
created: 2026-11-01
---

Every task output should link by CID to the assets it was made from, so the
asset graph's lineage is unbroken from raw reads to a cohort VCF. Today the
links stop partway through the GATK chain. Read from the code (the
`update()` calls in `src/stargazer/tasks/`), not measured:

| Task | Output | Links to its inputs |
|------|--------|---------------------|
| `bwa_mem`, `bwa_mem2_mem` | `Alignment` | `reference_cid`, `r1_cid` |
| `apply_bqsr` | `Alignment` | `reference_cid` only |
| `base_recalibrator` | `BQSRReport` | `alignment_cid` |
| `mark_duplicates` | `DuplicateMetrics` | `alignment_cid` |
| `sort_sam`, `mark_duplicates`, `merge_bam_alignment` | `Alignment` | none, only `sample_id` and `tool` |
| `haplotype_caller`, `combine_gvcfs`, `joint_call_gvcfs`, `apply_vqsr` | `Variants` | none by CID; `source_samples` and `build` |
| scRNA tasks | `AnnData` | `source_cid` |

So `assemble(reference_cid=ref.cid)` finds the raw alignment but not the
sorted, deduplicated BAM made from it, and a cohort VCF can be traced to
its samples by name but not to the exact BAMs or GVCFs. Two runs of the
same sample against different references are told apart only by `build`.

Opened from the docs revision that introduces the asset graph (ticket
[[asset-graph-docs]]), which states the convention: an output records what
it was made from.

## Shape

- An `Alignment` made from another records it: `alignment_cid` on
  `Alignment`, plus `reference_cid` carried forward, so a lineage query on
  the reference still finds every BAM made against it.
- `Variants` records its inputs: `alignment_cid` for a single-sample GVCF,
  and for a cohort the GVCFs' CIDs (a list, which round-trips as JSON) plus
  `reference_cid`.
- Mind the public tier's 9-keyvalue cap: `Variants` already declares 7
  fields, so a published cohort VCF with two more keys plus `_owner` is
  over it. Decide which link the public record keeps, or drop a field that
  duplicates another.

## Pieces

- [ ] Tasks tier tests first: each changed task's output carries its
      inputs' CIDs, and `assemble(<key>_cid=...)` finds it.
- [ ] Add the fields and set them in each task.
- [ ] Germline workflow on the devbox: from the cohort VCF, walk back to
      the reference by CID alone.
- [ ] Docs: `docs/architecture/types.md` lists the link fields.

## Plan

On `feat/provenance-on-every-output`. The public tier's cap decides the shape: `asset` and `_owner` leave a type 7 fields, and `Alignment` and `Variants` both have 7 today, so each link takes the place of something.

- **`Alignment`:** `r1_cid` becomes `source_cid`, the CID of what the BAM was made from: the R1 reads for an aligner's output, the alignment before it for every later step (the name scRNA's `AnnData` already uses). `reference_cid` is carried through every step, so `assemble(reference_cid=…)` finds every BAM made against a reference.
- **`Variants`:** `sample_count` goes (it's `len(source_samples)`), and `source_cids` takes its place, a list: the alignment for a GVCF, the GVCFs for a combined or joint-called file, the VCF for a VQSR-filtered one. No `reference_cid`: there's no room, and the reference is one walk away through the alignment. `build` stays as the key people query by.
- **Tasks:** `sort_sam` and `mark_duplicates` set `source_cid=alignment.cid` and carry `reference_cid`; `merge_bam_alignment` and `apply_bqsr` set `source_cid` and `reference_cid=ref.cid`; `haplotype_caller`, `combine_gvcfs`, `joint_call_gvcfs` and `apply_vqsr` set `source_cids`.
- **Tests:** each task's test file gets a test that stores its input (with its index as a companion where the tool needs one), runs the task and checks the link, by `assemble(source_cid=…)` for alignments. The devbox germline test walks from the cohort's VCF to the reference by CID.
- **Docs:** `docs/architecture/types.md`, the diagram in `docs/index.md`.

Blast radius: stored records keep their `r1_cid` and `sample_count` as extra keyvalues, which a typed asset carries in `keyvalues`. The community repo's `germline/short-variant-discovery.py` reads `cohort.sample_count` and needs `len(cohort.source_samples)` before the catalog moves to a release with this (ticket [[community-kernel-headers]] is editing it anyway). A cohort's `source_cids` grows with its GVCFs, as `source_samples` does; a public record's value limit hasn't been measured against a large cohort.

Related: [[board]].
