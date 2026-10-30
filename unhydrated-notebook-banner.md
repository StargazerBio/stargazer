---
title: unhydrated-notebook-banner
status: doing
priority: normal
created: 2026-10-30
---

A pod whose notebook isn't in `/workspace` after the hydrate opens it blank
and never saves it (`SG_UNSAVED_NOTEBOOK`, from ticket
`delete-running-notebook-resurrects`). That's right when the notebook was
deleted, since the pod is being torn down anyway. After a failed hydrate,
though, the user sees a blank notebook, and what they type into it is lost
without a word.

The save banner (`runtime/save_banner.html`, polling `/__sg__/save-status`)
already names files the pod won't save because they're too big. It should
name this one too, saying the notebook didn't load and edits here won't be
saved, so the user reloads instead of working in it.
