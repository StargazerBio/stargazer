---
title: Extra keyvalues on typed assets
status: doing
priority: high
created: 2026-10-09
---

A registered asset type rejects keys it doesn't declare, so a user who wants to record one more
field (`lane`, `library_id`) has to store the file under a made-up asset key, as a bare `Asset`
that no task can be handed. Let typed assets carry undeclared keys as strings in `keyvalues`,
kept through storage and queries, while declared fields keep their types and checks.

The plan is `.opencode/plans/29_open_asset_keyvalues.md` on branch `feat/open-asset-keyvalues`.
It moves into this ticket when that branch rebases onto main.
