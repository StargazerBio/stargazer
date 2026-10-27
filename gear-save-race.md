---
title: A running pod's save can overwrite a gear edit
status: doing
priority: low
created: 2026-10-21
---

The gear on a workspace tile rewrites a notebook's stored setup block while a running pod of that notebook holds its own copy. If the pod's save later stores its copy, the gear's change is lost. That's inferred from the code, not reproduced (ticket `notebook-environment`).

## Reproduced (2026-10-26, locally)

Through the real modules on a local store root (`app.workspace_store`,
`app.proxy`'s `hydrate_async`, `_seed_from_disk` and `sync_once`, and
`app.notebook_meta.replace_setup_body` as the gear calls it): after a gear
edit, an idle save pass saves nothing and the gear's setup block stays
stored. After one edit to a cell in the pod's copy, the next pass saves the
file and the stored setup block is the pod's old one. The pod saves any file
whose size or mtime changed and never rereads the store, so whatever it
saves overwrites the gear's edit. Not run on Union: marimo rewriting the
file when a cell is edited, which is how edit mode saves (inferred).

## Fix (decided 2026-10-26)

The gear refuses while the notebook has a running pod, in either mode. The
modal says to stop the notebook first, or to edit the setup block in the
notebook itself. `POST /workspace/setup` checks the user's `nb-*` apps the
way `/launch/status` does and answers 409 when the notebook's is up, so a
stale page can't get around it.

Test it: with a running app for the notebook, the save route answers 409 and
the stored notebook is unchanged; with none, the save goes through.
