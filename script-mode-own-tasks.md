---
title: script-mode-own-tasks
status: maybe
priority: low
created: 2026-11-10
---

A notebook run as a script (`python notebook.py`, marimo's script runner) can't call its own Flyte tasks: a cell that names an `@app.function` carrying an `@env.task` decorator fails with `NameError: name '<task>' is not defined`. The same notebook runs in marimo's kernel (`marimo edit`, `marimo run`, `marimo export html`), and the task is there when the notebook is imported as a module, so a cluster pod finds it.

Measured on marimo 0.25.2 with a twelve-line notebook: a setup block making a `flyte.TaskEnvironment`, one `@app.function` with `@env.task`, and a cell awaiting it. Without the `@env.task` line the script run works. Seen first in the community scRNA notebook (ticket [[community-kernel-headers]]), whose cells dispatch its own `preprocess` task.

To settle: whether it's marimo's to fix (report upstream) or the pattern's (the decorated object isn't a function, which may be what the script runner keys on), and whether any documented path runs a notebook as a script. The `verify-stargazer` skill's headless route uses the kernel.

## Findings (2026-11-16)

Not the pattern's fault. Two upstream gaps meet (measured on marimo 0.25.2, the latest on PyPI today, and flyte 2.12.4, with the twelve-line repro):

- marimo's `@app.function` builds its cell from the decorated object's source, `inspect.getsourcelines(obj)` in `toplevel_cell_factory` (`marimo/_ast/compiler.py`). `@env.task` returns an `AsyncFunctionTaskTemplate`, not a function, so that raises `TypeError`. `cell_decorator` (`marimo/_ast/cell_manager.py`) catches it and returns the object without registering a cell, which keeps imports working. A script run only defines what registered cells define, so later cells hit `NameError`. The kernel parses the file statically and never takes that path, which is why `marimo edit`, `run` and `export` work.
- Flyte's task template keeps the function as `.func` but sets no `__wrapped__`, so nothing generic (`inspect.unwrap`) gets back to it.

Proof: patching `toplevel_cell_factory` in-process to receive `obj.func` when it's a function makes the script run register the cell and print the task's result (`RESULT 6`). The cell's code then still carries `@env.task`, so the script run defines a real task. Putting `@env.task` above `@app.function` doesn't work around it: the cell's code then names `app`, which a cell can't see.

No doc, guide or skill runs a notebook as a script (grep of `docs/`, `.claude/skills/`, `runtime/`), and the `verify-stargazer` headless route uses the kernel, so nothing of Stargazer's is broken by it. What's left is reporting it upstream: marimo to unwrap (`inspect.unwrap`) before reading the source, and Flyte to set `__wrapped__` on its task templates (as `functools.update_wrapper` does), which together fix it for any decorator that wraps properly.

Related: [[board]], [[community-kernel-headers]].
