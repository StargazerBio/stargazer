---
title: Public notebooks
status: backlog
priority: normal
created: 2026-10-16
blocked_by:
  - publish-asset
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

**This is the open problem.** A hosted dashboard holds no Pinata key,
because its user can read its app spec, so any key baked into it reaches them.
Reading Pinata's public index needs a key, even for public files. Options:

- a Pinata key users are allowed to see, scoped to reading only. Not checked:
  whether Pinata can scope a key that narrowly.
- real secret injection into app pods, once Flyte supports it
  (`.opencode/reference/devbox_workarounds.md`, "`AppEnvironment(secrets=[...])` is silently
  dropped")
