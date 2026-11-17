---
title: infra-sdk-pin-bump
status: backlog
priority: normal
created: 2026-11-16
---

Infra pins a released `stargazer-bio`. The next bump, to a release carrying PRs 148 through 155, breaks infra's unit tier for two reasons, neither of which is infra's code (measured 2026-11-16 by installing stargazer `main` into a throwaway env from infra's lockfile; found in ticket [[drop-notebook-asset]]):

- Every test errors in setup: infra's `tests/conftest.py` patches `stargazer.utils.storage.default_client`, which ticket [[lean-task-bodies]] replaced with a cached `get_client()`. The fixture should patch `get_client` instead.
- `test_basic_template_declares_an_environment_on_notebook_base` fails: the basic template changed since the release (tickets [[bare-task-environments]], [[sdk-front-door]]).

With a shim for the first, 387 passed and only the second failed. The bump also makes the `NOTEBOOK_KEY` skip in `/assets/schema` dead code, since the SDK no longer registers `notebook`.

A PR in infra once a release carries these: bump the pin, fix the fixture and the template test, drop the dead skip, run infra's unit tier and its dashboard check on the tenant.

Related: [[board]], [[drop-notebook-asset]], [[lean-task-bodies]], [[sdk-front-door]].
