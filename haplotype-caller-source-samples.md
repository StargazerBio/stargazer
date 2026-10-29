---
title: haplotype-caller-source-samples
status: done
priority: high
created: 2026-10-09
pr: 31
---

`haplotype_caller` sets `source_samples` to a string, not a list; it
round-trips as a string, so `len()` counts characters (measured: 7 for
`"NA12829"`).

Found in the docs correctness sweep (2026-10-09, #18).

## Verification

Branch `fix/haplotype-caller-source-samples`. Measured 2026-10-14:

- New `tests/tasks/gatk/test_haplotype_caller.py` (tasks tier, gatk image)
  failed before the fix with `'NA12829_TP53' == ['NA12829_TP53']`, and passes
  after, both on the returned GVCF and after `assemble()` reads it back.
- Devbox: `tests/devbox/test_germline.py` passes (2 tests). The GVCF its
  `haplotype_caller` pod stored reads back from the dashboard's index with
  `source_samples` `["NA12829"]`. The three GVCF rows from 2026-10-09 runs
  of the old code hold the string `"NA12829"`.

## Outcome

Shipped in PR #31 (merged 2026-10-15). `haplotype_caller` stores
`source_samples` as a list, and it reads back as one.

Verified with a new tasks-tier test (a string before, a list after, both on
the returned GVCF and after `assemble()`) and the devbox germline workflow,
whose GVCF read back from the dashboard's index as `["NA12829"]`.

Left: GVCFs stored by earlier runs keep the string. The new test passed
`Alignment(format=...)`, which #37 removed; merged separately, the two broke
the tasks tier on `main` until #35 dropped the argument.
