---
title: Store the VQSR tranches file as a companion asset
status: review
priority: high
created: 2026-10-09
pr: 38
---

`variant_recalibrator` records the tranches file only as a path in its
own pod (`VQSRModel.tranches_path`) and never stores it, so
`apply_vqsr` in another pod can't read it (inferred from the code; no
test runs the two in separate pods). [Plan 27](archive/27_asset_storage_index.md)'s open Q20: the tranches
file should be its own companion asset.

Found in the docs correctness sweep (2026-10-09, #18).

The recal file's index (`.recal.idx`) was missing in the other pod too:
given the tranches, ApplyVQSR still fails with "must support random access"
(measured in the gatk image). Both are stored as companions of the model
in #38.
