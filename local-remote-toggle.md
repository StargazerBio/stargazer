---
title: In-notebook local-vs-remote toggle UI
status: backlog
priority: normal
created: 2026-05-19
---

Formalize the dispatch choice as a reusable `mo.ui` element (radio / segmented control) so individual cells don't need to hardcode `flyte.with_runcontext(mode="local").run` vs `flyte.run`.
