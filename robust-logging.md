---
title: robust-logging
status: later
priority: low
created: 2026-05-19
---

- [ ] Per-task tags so logs can be demultiplexed.
- [x] One logfile per workflow execution: `log_execution()` in `config.py`. Removed by [[split-config]]: in a task pod it had no repository and its file went with the pod; a run's record is Flyte's.
      opens one per run (seen 2026-10-14).
- [ ] Stop flushing to stdout/err to keep context windows clean.
- [ ] Env vars for log level and a bool to include actual tool-call output.

Related: [[board]].
