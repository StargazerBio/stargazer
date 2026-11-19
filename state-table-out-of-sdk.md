---
title: state-table-out-of-sdk
status: later
priority: low
created: 2026-11-16
---

The SDK's asset index (`src/stargazer/utils/index.py`) carries the dashboard's own state table: its schema (`_STATE_SCHEMA`), `state_table_name()`, `state_table_sql()`, the `state_table` property, and a note that `write` and `read` are public "so the dashboard can keep its own rows". Every index creates the table, a local user's SQLite file included, and nothing in the SDK reads it (measured 2026-11-16: its only users are infra's `app/user_state.py` and `stargazer_users/user_index.py`).

The idea: the state table's schema and name move to infra, beside `user_state.py`. The SDK's index keeps `read` and `write` as the way to run a statement on its connection, which is all the dashboard needs from it.

To settle: onboarding creates both tables on DSQL, where a user's login can't run DDL, so infra already owns that half. Locally and on the devbox the index creates the state table itself; infra would create it at dashboard start instead. Whether that's worth a contract change between the two repos for about forty lines.

Related: [[board]], [[asset-storage-index]], [[launch-build-state]].
