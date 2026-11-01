---
title: robust-logging
status: maybe
priority: low
created: 2026-05-19
---

- [ ] Per-task tags so logs can be demultiplexed.
- [x] One logfile per workflow execution: `log_execution()` in `config.py`
      opens one per run (seen 2026-10-14).
- [ ] Stop flushing to stdout/err to keep context windows clean.
- [ ] Env vars for log level and a bool to include actual tool-call output.

Related: [[board]].
