---
title: script-mode-own-tasks
status: backlog
priority: low
created: 2026-11-10
---

A notebook run as a script (`python notebook.py`, marimo's script runner) can't call its own Flyte tasks: a cell that names an `@app.function` carrying an `@env.task` decorator fails with `NameError: name '<task>' is not defined`. The same notebook runs in marimo's kernel (`marimo edit`, `marimo run`, `marimo export html`), and the task is there when the notebook is imported as a module, so a cluster pod finds it.

Measured on marimo 0.25.2 with a twelve-line notebook: a setup block making a `flyte.TaskEnvironment`, one `@app.function` with `@env.task`, and a cell awaiting it. Without the `@env.task` line the script run works. Seen first in the community scRNA notebook (ticket [[community-kernel-headers]]), whose cells dispatch its own `preprocess` task.

To settle: whether it's marimo's to fix (report upstream) or the pattern's (the decorated object isn't a function, which may be what the script runner keys on), and whether any documented path runs a notebook as a script. The `verify-stargazer` skill's headless route uses the kernel.

Related: [[board]], [[community-kernel-headers]].
