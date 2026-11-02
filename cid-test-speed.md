---
title: cid-test-speed
status: maybe
priority: low
created: 2026-11-01
---

`tests/utils/test_cid.py` spends about 2.4 s of the unit tier generating its 45 MB input. A faster generator changes the bytes, so the CIDs the test pins would have to be recomputed with kubo, the reference implementation they're checked against. Worth it only if the unit tier's time starts to matter. Raised in [[test-consolidation]].

Related: [[board]].
