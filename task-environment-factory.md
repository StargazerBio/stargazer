---
title: task-environment-factory
status: review
priority: normal
created: 2026-11-09
pr: 147
---

What every task environment shares is a convention, not a call. Each `flyte.TaskEnvironment` that runs Stargazer tasks has to be given three things by hand: `image=task_image(__file__)` (or `notebook_image(__file__, name)`), `env_vars=STARGAZER_ENV_VARS` and `secrets=STARGAZER_SECRETS`. The two domain `env.py` files and every notebook that defines its own tasks (`notebooks/tutorials/tasks.py`, the templates) repeat them. Leaving out `env_vars` in a notebook is silent: the pod has no store root or index URL, writes its outputs to its own disk, and the next pod can't find them. Found in a review of the core (2026-11-09); read from the code, not reproduced.

The same review found the domains listed three ways: `cli/lock_envs.py` globs `env.py` files, `cli/publish_task_images.py` globs and imports them, and `cli/docker_task_tests.py` keeps a hand-written `IMAGES` dict.

## Plan

On `refactor/task-environment-factory`. Two factories in `stargazer.config`, beside the image recipes they wrap:

```python
def task_environment(env: str | Path, **kwargs) -> flyte.TaskEnvironment:
    """A domain's environment, named after its directory, on `task_image(env)`."""

def notebook_task_environment(notebook: str | Path, name: str, **kwargs) -> flyte.TaskEnvironment:
    """A notebook's own tasks' environment, on `notebook_image(notebook, f"stargazer-{name}")`."""
```

Both pass `env_vars=STARGAZER_ENV_VARS` and `secrets=STARGAZER_SECRETS`, and `**kwargs` (`description`, `resources`, anything else `TaskEnvironment` takes) straight through. A caller that passes `env_vars` or `secrets` adds to the shared ones (dict merge, list concat), never replaces them.

- [x] Unit tests first (`tests/unit/test_environments.py`): `task_environment(<tmp>/tasks/demo/env.py with a header>)` is named `demo`, its image `stargazer-demo`, and carries the shared env vars and the Pinata secret; a caller's extra `env_vars` are merged; same for the notebook factory with `name="tutorial"` → image `stargazer-tutorial`.
- [x] The factories. `STARGAZER_ENV_VARS` and `STARGAZER_SECRETS` stay importable (the infra repo may read them), but nothing in this repo outside `config.py` uses them.
- [x] `tasks/gatk/env.py`, `tasks/scrna/env.py`: `gatk_env = task_environment(__file__, description=..., resources=...)`. The built images must not change: compare `gatk_env.image.uri`/name and the env's serialized spec before and after.
- [x] Notebooks that define a task environment (`grep -rn "notebook_image(" src/stargazer/notebooks`): use `notebook_task_environment`.
- [ ] One list of domains: a `task_environments()` helper in `cli/` (or `stargazer.tasks`) that imports each `tasks/*/env.py` and yields its `TaskEnvironment`; `publish_task_images.py` and `docker_task_tests.py` use it. `docker_task_tests.py` maps a `tests/tasks/<dir>` with no `env.py` of its own (`general`) by which env its tasks are decorated with, or keeps that one mapping explicitly.
- [x] Docs: `AGENTS.md`'s "When defining a new TaskEnvironment" rule, `docs/architecture/configuration.md`, `docs/architecture/tasks.md`, the guides that show an environment, the wiki's images page.

Assumptions made instead of asked: the factories live in `config.py` rather than a new module, since the recipes they wrap are there and a split isn't needed yet; the domain's directory name stays the environment's name.

## Evidence (2026-11-09)

Typed by a cheap worker from the plan, diff read in full. The new tests failed first (`config` has no `task_environment`); then 186 passed across `tests/unit`, `tests/notebooks` and `tests/assets`. `gatk_env`, `scrna_env` and `tutorial_env` have the name, image name, description, resources, env vars and secrets they had. One task test per domain passes in an image built from the new `env.py` (`test_create_sequence_dictionary.py`, `test_normalize.py`). All measured. Not run: the whole tasks tier, and a notebook task on a cluster.

Left out of PR 147: the one list of domains. `IMAGES` in `cli/docker_task_tests.py` is three lines and says which image `general`'s tests run in, which a glob can't; it stays until a third domain makes it a chore.

## Verification recipe

- Unit tier, then the tasks tier (`pixi run python cli/docker_task_tests.py`), which builds both images from the new `env.py` files.
- A tutorial notebook's task dispatched "On the cluster" on the devbox stores its output where the next cell's `assemble()` finds it.

Related: [[board]], [[asset-core-tidy]], [[lean-task-bodies]], [[flyte-images]].
