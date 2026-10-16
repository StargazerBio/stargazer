---
title: Public notebooks
status: backlog
priority: normal
created: 2026-10-16
blocked_by:
  - notebooks-as-assets
  - publish-asset
---

Once notebooks are assets (ticket `notebooks-as-assets`), making one public
works like making any other asset public. A Publish button on a notebook calls
`publish(asset)` (ticket `publish-asset`). That puts the notebook on Pinata's
public network, with the same CID and its keyvalues. The dashboard's Notebooks
section then lists public notebooks next to the user's own. Opening a public
notebook for editing saves the user's edits as their own private notebook, so
the copy needs no separate action.

**The open problem is the listing.** A hosted dashboard holds no Pinata key,
because its user can read its app spec, so any key baked into it reaches them.
Reading Pinata's public index needs a key, even for public files. Options:

- a Pinata key users are allowed to see, scoped to reading only. Not checked:
  whether Pinata can scope a key that narrowly.
- real secret injection into app pods, once Flyte supports it
  (`.opencode/reference/devbox_workarounds.md`, "`AppEnvironment(secrets=[...])` is silently
  dropped")
