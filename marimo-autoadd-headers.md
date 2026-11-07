---
title: marimo-autoadd-headers
status: review
priority: low
created: 2026-11-04
pr: 136
---

In a hosted notebook pod, running the Execution tutorial's cells made marimo add `flyte==2.12.4` to `execution.py`'s header with `pixi add --script`. The pod log shows `Adding to sandbox: /usr/local/bin/pixi add --script /stargazer/src/stargazer/notebooks/tutorials/execution.py --pypi flyte==2.12.4`. The file lives in `/stargazer`, so nothing is saved, but marimo rewrites a built-in notebook's header and may re-solve its environment on open, which would cost the prebuilt environment its speed.

To check:
- whether the uv sandbox did the same before pixi;
- whether the tutorials' headers should list `flyte` themselves, or marimo's package auto-add should be off in the pod.

Seen while verifying [[notebook-dockerignore]].

## Findings (2026-11-07)

- **What adds it** (read in marimo 0.25.1, the image's): `marimo edit --sandbox` turns on script-metadata management for the session (`_server/start.py`), with no setting to turn it off; only dropping `--sandbox` does. On each cell's registration the kernel hands its new top-level imports to the sandbox's `record_dependencies` (`_environments/sandbox.py`), which skips `marimo` and every name already in the header's `dependencies` (not `[tool.pixi.pypi-dependencies]`), and writes the rest at the version the environment has, as `name==version`. `flyte` is imported by four notebooks (the Tasks and Execution tutorials, the basic and blank templates) and comes in only through `stargazer-bio`, so it is recorded; `stargazer` maps to no installed distribution and is skipped.
- **The uv sandbox did the same** (inferred from code): the uv-sandbox image (`debug:warm-uv-cache`) ran the same marimo 0.25.1 under `--sandbox`, and `record_dependencies` is the same for both backends; it ran `uv add --script` instead.
- **It doesn't cost the prebuilt environment its speed** (measured in `debug:notebook-dockerignore`, amd64 emulated): `pixi add --script execution.py --pypi flyte==2.13.0` takes 0.3 s, and the next `pixi install --script` 1.9 s against a 1.7 s no-op. pixi keys the environment on the path, so the header edit reuses it.
- **The rewrite also relinks the environment** (measured by the `released-sdk-in-notebooks` session): the install after a header change relinks the tutorial's PyPI packages as symlinks into the uv cache, and with a non-editable SDK that broke Flyte's code bundle until that branch's `_bundle_root()` fix.
- **The harm is the pin.** A template is opened as a copy in `/workspace`, so the `flyte==<image's version>` marimo writes is saved to the user's store with it. Once the image moves to a newer flyte, that notebook's environment still asks for the old one, which isn't in the image's cache, and its kernel runs a different flyte from the SDK's (inferred). In a built-in tutorial the edit is lost at the pod's end but rewrites the header the user sees.
- **The fix: the headers list `flyte` themselves**, unpinned like `marimo`, so marimo leaves it alone and `stargazer-bio`'s range decides the version.

## Plan

- [x] Test (`tests/notebooks/`): every third-party top-level import of a built-in notebook maps to a distribution its header's `dependencies` names, `marimo` and the SDK aside, the check marimo's auto-add makes. It fails on the four notebooks today.
- [x] `"flyte"` in the `dependencies` of `tutorials/tasks.py`, `tutorials/execution.py`, `templates/basic.py` and `templates/blank.py`.
- [x] Verified in a hosted pod: the Execution tutorial's cells run and its file is left unchanged (evidence below; the pod log wasn't read).

Seen alongside, a ticket of its own: `marimo-server-layer-symlinks`.

## Verification recipe: built-in headers list flyte

A hosted notebook pod running the Execution tutorial leaves its header alone: marimo doesn't add `flyte` to it.

### Sub-features

- **H1**: running the Execution tutorial's cells in a hosted edit pod logs no `pixi add --script`.
- **H2**: a basic-template notebook created from the dashboard, run the same way, keeps a header with no `flyte==` pin. Reachable only once a release carries the template: the dashboard seeds new notebooks from the stargazer release it pins.

### How to get to it (user POV)

The dashboard's Tutorials section, Execution, Edit; for H2, a new notebook from the basic template.

### Driving it

Preconditions: the branch's image pushed as `ghcr.io/stargazerbio/debug:marimo-autoadd-headers`; the infra checkout with `tenant.env` loaded; the u-pryce dashboard not in use by another session (check `union_dashboard.py check dashboard`'s `STARGAZER_NOTEBOOK_IMAGE`).

1. From infra: `STARGAZER_NOTEBOOK_IMAGE=ghcr.io/stargazerbio/debug:marimo-autoadd-headers uv run python .claude/skills/verify-dashboard/scripts/union_dashboard.py deploy`. Passes: prints the dashboard URL.
2. Sign in to the console as the test account, open the dashboard, launch Execution in edit mode, and run every cell (the local run is enough). Passes: the cells finish.
3. Read the tutorial's file through marimo's file API from the notebook page (`fetch('/api/files/file_details', {method: 'POST', headers: {'Content-Type': 'application/json', 'Marimo-Server-Token': document.querySelector('marimo-server-token').dataset.token}, body: JSON.stringify({path: '/stargazer/src/stargazer/notebooks/tutorials/execution.py'})})`) and hash its `contents`. Passes: the sha256 of the branch's `execution.py`, and `lastModified` before the cells ran. With the AWS `claude` profile signed in, the pod log is the second check: `kubectl --kubeconfig <eks kubeconfig> logs -n u-pryce-development <nb-execution-edit pod> | grep -c "pixi add --script"` (read-only) prints `0`.
4. Teardown: `union_dashboard.py teardown`. Passes: `live runs: []`.

### Gotchas

- A launch from `fetch('/launch')` that needs an image build settles only when `/launch/status` is polled, as the dashboard page does.
- marimo's terminal didn't take typed input from the built-in browser pane; the file API needed no typing.

- The u-pryce dashboard is shared between sessions; a deploy replaces another session's image.
- A local, emulated container is no stand-in: the editor's kernel never connected there, and with the main image's server layer rebuilt at start the editor loads blank (ticket `marimo-server-layer-symlinks`).

## Evidence (2026-11-07)

- Test against main's notebooks: 4 failed (basic, blank, execution, tasks, each `['flyte']`), 2 passed; on the branch `tests/notebooks/` passes (18).
- H1, measured on the tenant with `ghcr.io/stargazerbio/debug:marimo-autoadd-headers` (sha256:9917d39f…): every Execution cell ran without errors, cluster runs `umvgj796kpjhcrlmfqc9` and `ujkvwvr8j7phl96z8klr` succeeded, and afterwards the tutorial's file in the pod hashed to the branch's (`e3010c8c…`), last modified 17:55:37 UTC (the image build) against cells run at about 18:17.
- H2 not reached: the notebook the dashboard created from the basic template had the 2026.10.30 release's header (`[tool.uv.sources]`, no pixi section), and its kernel didn't start in about four minutes.
- Torn down: `union_dashboard.py teardown` stopped `nb-execution-edit` and `dashboard`, live runs `[]`; the test workspace notebook deleted.

Related: [[board]], [[notebook-dockerignore]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
