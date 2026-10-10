---
title: haplotype_caller stores source_samples as a string
status: backlog
priority: high
created: 2026-10-09
---

`haplotype_caller` sets `source_samples` to a string, not a list; it
round-trips as a string, so `len()` counts characters (measured: 7 for
`"NA12829"`).

Found in the docs correctness sweep (2026-10-09, #18).
