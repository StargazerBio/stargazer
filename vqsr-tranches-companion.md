---
title: Store the VQSR tranches file as a companion asset
status: backlog
priority: high
created: 2026-10-09
---

`variant_recalibrator` records the tranches file only as a path in its
own pod (`VQSRModel.tranches_path`) and never stores it, so
`apply_vqsr` in another pod can't read it (inferred from the code; no
test runs the two in separate pods). [Plan 27](archive/27_asset_storage_index.md)'s open Q20: the tranches
file should be its own companion asset.

Found in the docs correctness sweep (2026-10-09, #18).
