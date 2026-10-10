---
title: stargazer promote-task CLI
status: backlog
priority: low
created: 2026-06-10
---

The mechanical step of task promotion — extract the cell function via `ast` (marimo files are valid Python), drop it into the target `src/stargazer/tasks/` module with decorator and types intact, generate a skeleton test, open a PR via the server-side GitHub flow. Waiting for real usage patterns to inform the exact UX. (Was a Roadmap note in `docs/architecture/notebook.md`.)
