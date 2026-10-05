---
name: bug-fix
description: Reproduce, root-cause, and fix a reported Stargazer defect with runtime evidence. Use when the user reports a bug, a failing task or workflow run, a broken notebook or app page, or a regression, and before changing any code to fix it.
---

# Bug fix

Every shipped line traces to runtime evidence. A change that "might help" is a hypothesis, not a fix, and it does not ship. The smallest change the evidence justifies ships, nothing more.

Adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack)'s bug-fix playbook (MIT).

## 1. Reproduce it yourself

Reproduce on the same surface the bug was reported on. A bug reported against a devbox run is not reproduced by a passing local run.

| Surface | Reproduce with |
|---|---|
| SDK task or workflow, local | `flyte.with_runcontext(mode="local").run(task, ...)` in a script under `scratch/` or a pytest case |
| SDK task or workflow, remote | `flyte.run(...)` against the devbox. Check `.opencode/reference/devbox_workarounds.md` first, a known quirk may already explain it |
| Notebook | `marimo run` or `marimo export` on the notebook, or the smoke test in `tests/notebooks/` |
| MCP server | the `mcp__stargazer__*` tools directly |
| App tier (`app/`) | curl against the served app, or Claude in Chrome for pages and flows |

Do not ask the user to reproduce. Ask only with a specific reason the surface is out of reach (credentials you lack, a cluster that is down), and only after driving it as far as it goes. If it won't fire, tighten conditions or add logging until it does.

## 2. Find the cause by elimination

List the candidate causes. Take the check that rules out the most candidates at once, get runtime evidence (a log line, a printed value, a run), and eliminate. Repeat until one survives. When program state is unclear, add temporary logging and read it as the code runs. Don't guess.

Before settling on a cause, check the history: `git log -S '<symbol>'` and `.opencode/plans/archive/` often say why the code is shaped the way it is.

Confirm the surviving mechanism with evidence before writing the fix. "The error went away" is not a mechanism.

If two fixes built on the same assumption have failed, stop fixing and question the assumption.

## 3. Fix at the root

Fix where the cause lives, not where the symptom shows. No `None` guards, broad `except`, or retries that silence the failure without explaining it. Revert any change made for a hypothesis that turned out wrong, including temporary logging.

## 4. Verify on the same surface

The step-1 repro now passes, on the same surface. An inconclusive result or a different surface is not a pass, say so. A passing unit test shows branch behavior, not that the bug is gone.

## 5. Lock it in

When there is a cheap local test path, add a regression test that fails before the fix and passes after, per the test rules in `AGENTS.md`. When the only real test needs the devbox, Pinata, or a long tool run, keep the repro script instead and say so.

If the bug came from a devbox or deployment quirk, append it to `.opencode/reference/devbox_workarounds.md`.

## Reply

What was broken, the root cause, the fix, and how you verified it. Paste the failing-then-passing repro output verbatim. Label anything you did not observe directly as inferred or a guess.
