---
title: Public notebooks
status: backlog
priority: normal
created: 2026-10-16
blocked_by:
  - publish-asset
  - dashboard-pinata-key
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

## The tutorials and the scRNA notebook

**They leave the SDK and are published as public notebooks** (decided
2026-10-16). That means `src/stargazer/notebooks/tutorials/` and
`src/stargazer/notebooks/workflows/`. The dashboard's Tutorials and Workflows
sections go with them, and so does Copy to workspace.

**The tutorials' imports have to change.** The tutorials import each other as
`stargazer.notebooks.tutorials.*`: Tasks and Workflows import the Assets
tutorial's `SampleSheet`, and Execution imports the Workflows tutorial's
workflow. That path goes once they leave the package. As public assets, they
can import each other as plain modules if they sit side by side, the way a
user's own notebooks do in `/workspace`. Still open: does opening one
tutorial fetch the whole set, or does the user copy the set into their
workspace?

The `scrna-pipeline` feature in `verify-stargazer` drives the scRNA notebook
from its path in the package, so it has to change too.

## Reading the public tier

Hosted dashboards read Pinata's public index once they have the key as a
secret (ticket `dashboard-pinata-key`). Union injects app secrets without
putting the value in the app record (measured 2026-10-17).
