---
title: asset-graph-docs
status: review
priority: normal
created: 2026-11-01
pr: 123
---

Rewrite the docs people meet first around Stargazer's two killer
features, on one concise Home page: production-grade notebooks (the same
cell runs on exploratory data in the notebook or fanned out across a
cluster, with one switch), first so readers are grounded, then the asset
graph (data that knows what it is), with "collaboration without
coordination" naming what it makes possible. A separate Asset Graph page
was tried and folded back into Home: the two repeated each other, and it
left notebooks with one paragraph. The term "asset graph" is used across the docs and the Assets
tutorial.

Claims are held to what's true today. Three gaps found while planning are
their own tickets: [[publish-with-companions]],
[[reuse-reference-companions]] and [[provenance-on-every-output]].

- [x] `docs/index.md` rewritten to lead with the system
- [x] New `docs/asset-graph.md`, in nav after Home
- [x] "Asset graph" through the overview, types, tasks, workflows,
      notebook and getting-started docs
- [x] Assets tutorial: section 7 reframed as the payoff, a section on
      extending the graph with extra keys, run headless

Related: [[board]].
