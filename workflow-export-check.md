---
title: workflow-export-check
status: done
priority: low
created: 2026-10-15
pr: 59
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

## Verification

Branch `test/workflow-export-check`, PR #59.

- `test_discovery_finds_every_defined_workflow` walks every module under
  `stargazer.workflows` with the task test's helper, which now takes the
  package to walk. I dropped `scrna_clustering_pipeline` from `__all__` and
  from the old hand-kept list. The old tests passed, and the new test failed
  on exactly that name.
- Correction: `germline_short_variant_discovery` does import
  `prepare_reference`. It's the same object, and the registry reads only the
  package's `__all__`, so the skip never fired (measured on `main`). Without
  the skip, a workflow with the same name as a task replaces the task's entry
  in the registry. A throwaway `samtools_faidx` workflow showed that this fails
  the task walk test.
- `to_catalog()` is byte-identical to `origin/main`'s. The unit tier passes
  (501).

## Outcome

PR #59 (`5bd1a96`, merged 2026-10-21). `test_discovery_finds_every_defined_workflow`
walks the modules under `stargazer.workflows` with the task test's helper,
and the registry no longer skips a workflow whose name is already
registered. Verified as above. Nothing left.
