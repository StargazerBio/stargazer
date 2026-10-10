---
title: More robust logging
status: backlog
priority: low
created: 2026-05-19
---

- Per-task tags so logs can be demultiplexed.
- One logfile per workflow execution.
- Stop flushing to stdout/err to keep context windows clean.
- Env vars for log level and a bool to include actual tool-call output.
