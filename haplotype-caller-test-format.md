---
title: HaplotypeCaller test still passes the removed Alignment.format
status: doing
priority: high
created: 2026-10-15
---

`tests/tasks/gatk/test_haplotype_caller.py` (from #31) builds an `Alignment`
with `format="bam"`, and #37 removed `Alignment.format`. They merged
separately, so the tasks tier on `main` fails with `TypeError:
Alignment.__init__() got an unexpected keyword argument 'format'`. Found
running the tasks tier for `fetch-pulls-dependents` (2026-10-15).

## Verification

Branch `fix/haplotype-caller-test-format`, 2026-10-15: without `format`, the
test passes in the gatk image (`cli/docker_task_tests.py
tests/tasks/gatk/test_haplotype_caller.py`, 1 passed).
