---
title: normalize stores normalized counts in the counts layer
status: backlog
priority: high
created: 2026-10-09
---

`normalize` copies `X` into `layers["counts"]` after `normalize_total`,
so the layer holds normalized counts (every row sums to ~498 on the
fixture), while its docstring, and `find_markers`, which tests on that
layer, say raw counts (measured).

Found in the docs correctness sweep (2026-10-09, #18).
