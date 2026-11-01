---
title: notebook-pinata-key
status: done
priority: normal
created: 2026-10-18
pr: 44
---

Hosted notebook pods get the org's Pinata key, as a Flyte secret, the way
dashboards do (ticket [[dashboard-pinata-key]]). Without it a notebook sees
only the user's own store: public data doesn't join its queries, and
publishing a stored file from a notebook (ticket [[publish-asset]]) raises.
Tasks and dashboards already have the key, so any user can already reach it
from a task they run (decided 2026-10-18: "put the pinata key everywhere").

## Design

`per_notebook_env` declares `secrets=STARGAZER_SECRETS`, the same list the
task environments and the dashboard declare. Union injects it and keeps only
a reference in the app's spec (measured 2026-10-17, ticket
[[dashboard-pinata-key]]). The devbox drops app secrets, so a devbox notebook
still has no public tier.

**The terminal doesn't get it.** The proxy scrubs secret-shaped vars from
the dropdown terminal's env (`_shell_env` in `app/proxy.py`), and it names
`PINATA_JWT` as one. A first version let the key through (`eea1456`); it was
reverted on review (`f941beb`, decided 2026-10-18). An agent running `env`
in the terminal would put the key in its context, the likeliest way for it
to leak by accident. The scrub is tidiness, not a boundary: any notebook
could already get the key through a task that declares the secret (under
Verified).

## Pieces

- [x] `app/per_notebook.py`: the secret on the notebook env. A test in
      `tests/unit/test_per_notebook.py`: the built env declares `PINATA_JWT`
      as a secret, and no env var holds it.
- [x] ~~`app/proxy.py`: the terminal keeps `PINATA_JWT`.~~ Reverted: the
      terminal still scrubs it, and `test_shell_env_scrubs_named_secrets` is
      back.
- [x] Docstrings and docs that say notebook pods carry no credential:
      `app/per_notebook.py`, `app/config.py`,
      `docs/architecture/configuration.md`,
      `.opencode/reference/architecture/app_internals.md`,
      `.opencode/reference/devbox_workarounds.md`.
- [x] Verify on Union with the test account: launch a notebook from a
      dashboard deployed from the branch, and in the pod the key is set
      (its length only) and Pinata accepts it; the app's spec holds only a
      reference. Stop every app the check started.

## Verified (Union, 2026-10-18)

- **Before**, `main`'s `per_notebook_env` served under a throwaway owner:
  `PINATA_JWT` unset; the notebook's Python had no public tier, and
  `query({"asset": "reference"})` returned 0 rows. **Correction
  (2026-10-18):** both checks ran through the terminal, which scrubs
  `PINATA_JWT` either way, so they couldn't show what the pod had. Rechecked
  from the marimo process's own env, on `main` at `b8e3a4e`: no
  `PINATA_JWT` and no `_UNION_PINATA_JWT`, but `_UNION_EAGER_API_KEY` is
  there. From that pod, notebook code with that env submitted a ten-line
  task declaring the org's `PINATA_JWT` secret, and the task saw the key:
  687 characters, sha256 prefix `93946e8f` (run `ujgbbqc4xtlwgbb2hjst`). So
  before this change the key was one deliberate step away from any
  notebook, not out of reach.
- **The secret alone:** the marimo process had the key (687 characters,
  sha256 prefix `93946e8f`, the local Pinata key's), and with its env the
  same query returned 1 public record. The terminal still showed it unset.
- **Both commits, on the branch's image (`notebook-app-c83b3fca…`):**
  - In a probe, marimo had `PINATA_JWT`, `_UNION_EAGER_API_KEY` and
    `_UNION_PINATA_JWT`, and the terminal only `PINATA_JWT`.
  - Then the dashboard, deployed from `eea1456`, ran `/launch` for the assets
    tutorial in Edit mode. In that pod's terminal the key was set and the
    SDK's query returned the public record.
  - The spec only references the secret.
- Everything started was stopped; no live runs.

## Outcome

Merged in #44 (2026-10-18). Hosted notebook pods declare the org's
`PINATA_JWT` as a Flyte secret, as dashboards and every task environment
do, so notebook code and tasks run inside a notebook see the public tier and
can publish. The dropdown terminal still scrubs it: a first version let it
through, and that was reverted on review (`f941beb`). Verified on Union
(above): the notebook process had the key and a public query returned the
public record; the terminal showed it unset; the app's spec only references
the secret.

The key was never out of reach: on `main` before this, notebook code got it
through a ten-line task declaring the secret (run `ujgbbqc4xtlwgbb2hjst`).
Keeping it private is ticket [[private-pinata-key]] (`maybe`).
