---
title: marimo-autoadd-headers
status: doing
priority: low
created: 2026-11-04
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
- **The harm is the pin.** A template is opened as a copy in `/workspace`, so the `flyte==<image's version>` marimo writes is saved to the user's store with it. Once the image moves to a newer flyte, that notebook's environment still asks for the old one, which isn't in the image's cache, and its kernel runs a different flyte from the SDK's (inferred). In a built-in tutorial the edit is lost at the pod's end but rewrites the header the user sees.
- **The fix: the headers list `flyte` themselves**, unpinned like `marimo`, so marimo leaves it alone and `stargazer-bio`'s range decides the version.

## Plan

- [ ] Test (`tests/notebooks/`): every third-party top-level import of a built-in notebook maps to a distribution its header's `dependencies` names, `marimo` and the SDK aside, the check marimo's auto-add makes. It fails on the four notebooks today.
- [ ] `"flyte"` in the `dependencies` of `tutorials/tasks.py`, `tutorials/execution.py`, `templates/basic.py` and `templates/blank.py`.
- [ ] Verified in a hosted pod: the Execution tutorial's cells run and the pod log has no `pixi add --script`.

Seen alongside, a ticket of its own: `marimo-server-layer-symlinks`.

Related: [[board]], [[notebook-dockerignore]], [[pixi-notebook-sandbox]], [[marimo-sandbox]].
