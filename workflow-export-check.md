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

Do the same for workflows. The task walk should carry over unchanged. While
there, drop `test_duplicate_prepare_reference_not_duplicated` and the
registry's skip for a workflow name that's already registered:
`prepare_reference` is now defined only in `gatk_data_preprocessing` and no
other workflow module imports it, so neither guards anything.
