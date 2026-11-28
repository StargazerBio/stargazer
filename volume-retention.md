---
title: volume-retention
status: later
priority: low
created: 2026-11-27
---

Every version of every workspace notebook's volume is kept, and nothing removes a volume once nothing names it. Storage only grows, by a version per save pass that found a change (30 s of active editing by default).

What piles up:

- **Versions.** Each commit is a version; none is ever pruned.
- **Deleted notebooks' volumes.** Delete removes the manifest and leaves the volume.
- **Forks nothing finalized.** An edit pod that dies without SIGTERM leaves its fork unsealed. A run-mode pod's throwaway fork is abandoned at shutdown, but not if the pod dies first.
- **Volumes a lost create left.** The dashboard's create makes the volume before its create-only manifest write; a write that loses the race leaves a sealed volume no manifest names.

Waiting on Union to ship retention for volumes. The SDK has no list or delete API, and an S3 lifecycle rule can't do it: an untouched notebook's only version would expire, and an old chunk can back the newest version. The aim is a month of versions, with each notebook's latest kept however old.

Related: [[board]], [[union-volumes]]
