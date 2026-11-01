---
title: conditional-workspace-writes
status: maybe
priority: low
created: 2026-10-30
---

A pod's save pass checks that a file it holds is still in the store
(`flyte.storage.exists`) before uploading it, so a notebook deleted from the
dashboard isn't put back (ticket [[delete-running-notebook-resurrects]]). The
check and the upload aren't atomic: a pass whose check runs just before a
delete still uploads just after it. With the dashboard deleting from the store
before it stops the pods, that takes a pass already running at the moment of
the delete. Not seen in testing.

Closing it would take a conditional write: an S3 `If-Match` on the ETag the
pod last read or wrote (obstore's `PutMode` update), so an upload over a
deleted or replaced object fails instead. `flyte.storage` doesn't expose that,
so it means reaching past it to the store. Worth it only if the window shows
up in practice.
