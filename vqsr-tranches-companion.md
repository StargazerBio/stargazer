---
title: vqsr-tranches-companion
status: done
priority: high
created: 2026-10-09
pr: 38
---

`variant_recalibrator` records the tranches file only as a path in its
own pod (`VQSRModel.tranches_path`) and never stores it, so
`apply_vqsr` in another pod can't read it (inferred from the code; no
test runs the two in separate pods). [[asset-storage-index|Plan 27]]'s open Q20: the tranches
file should be its own companion asset.

Found in the docs correctness sweep (2026-10-09, #18).

The recal file's index (`.recal.idx`) was missing in the other pod too:
given the tranches, ApplyVQSR still fails with "must support random access"
(measured in the gatk image). Both are stored as companions of the model
in #38.

## Outcome

Merged in #38 (2026-10-16). `variant_recalibrator` stores the tranches file
and the recal file's index as companions of the `VQSRModel`
(`VQSRTranches`, `VQSRModelIndex`), and `tranches_path` is gone. Verified on
the devbox with each task in its own pod: on `main`, `apply_vqsr` failed
reading the first pod's tranches path (run `r5v2wq7pqds2krnqzvkr`); on the
branch both tasks succeeded (runs `rl7r5j2wnw92gmgdqmvj`,
`rmt47gkhmm6wrss2njx8`). `tests/tasks/gatk/test_vqsr.py` runs apply through
a second storage client sharing only the store and index, and failed before
the fix. Left: VQSR runs only in INDEL mode on the fixtures, since Mills
holds no SNPs, so SNP mode isn't tested.

Related: [[gatk]].
