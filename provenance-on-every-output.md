---
title: provenance-on-every-output
status: backlog
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
`asset-graph-docs`), which states the convention: an output records what
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
