---
title: Check workflow exports against the workflow modules
status: backlog
priority: low
created: 2026-10-15
---

`test_discovery_finds_all_workflows` compares the registry to a hand-kept list
of workflow names, so a workflow left out of `stargazer.workflows.__all__` is
left out of the list too and the test still passes. That's how the scRNA tasks
went unexported (ticket `export-scrna-tasks`), whose fix replaced the task test
with a walk over the modules under `stargazer.tasks`.

Do the same for workflows. The walk needs one rule the task version doesn't:
workflow modules re-define tasks with the same short name
(`prepare_reference` is in two modules), which the registry registers once.
