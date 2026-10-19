---
title: Public notebooks
status: backlog
priority: normal
created: 2026-10-16
---

A notebook in a user's workspace is a plain file (ticket
`save-whole-workspace`). It becomes an asset when it's published (decided
2026-10-17). A Publish button on a workspace notebook builds a `Notebook`
asset from the file and calls `publish(asset)` (ticket `publish-asset`). That
puts the notebook on Pinata's public network, with its CID and keyvalues. The
dashboard then lists public notebooks next to the user's own. Opening a public
notebook for editing copies it into the user's workspace, where it's saved
like any other file.

**The `Notebook` asset type** lives in `src/stargazer/assets/notebook.py`,
with `_asset_key = "notebook"` and the fields `title` and `description`, taken
from the notebook's header when it's published. Nothing else creates one.

## Notebooks in the repo

**They aren't published** (decided 2026-10-17, replacing the 2026-10-16 plan
to publish the tutorials and the scRNA notebook). GitHub already makes them
public. The tutorials stay in the SDK and the dashboard's Tutorials section,
and the scRNA notebook moves to a top-level `notebooks/` folder (ticket
`top-level-notebooks`). Publish is for workspace notebooks only.

## Reading the public tier

Hosted dashboards have the Pinata key as a secret (ticket
`dashboard-pinata-key`, merged as #40), so they can read Pinata's public
index. Union injects app secrets without putting the value in the app record
(measured 2026-10-17).
