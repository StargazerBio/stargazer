---
title: test-consolidation
status: done
priority: normal
created: 2026-11-01
pr: 117
---

The test suite checked the same things in several places: the asset tests restated defaults and round trips up to five times, the tasks tier had an export test per task, and the postgres and dsql tiers imported the index tests by name, so a new one ran on SQLite alone. Consolidate without dropping any behavior only tested once.

## Outcome

Shipped in PR #117 (merge `85aba15`), from a branch with no ticket of its own; this one records it. The asset tests are two files, the per-type cases one test parametrized over every SDK type; the seeded fixture store (`seed.py`, `fixtures_db`) is gone, since no task test read it; the index tests are `TestIndexContract`, imported whole by each backend's tier. Unit tier 290 to 242 tests (22.6 s to 14.4 s), tasks tier 57 to 35, pinata 11 to 9. Verified by the unit and postgres tiers, the tool-free task tests in the dev venv, and mutation checks that each failed as expected. Not run: the tasks tier in its images, and the pinata, dsql and devbox tiers. Left: [[untested-tasks]] (which starts by running the tasks tier in its images) and [[cid-test-speed]]. No review comments.
