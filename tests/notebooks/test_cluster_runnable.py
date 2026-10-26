"""Notebook workflows a cluster pod can load.

A pod finds the task it runs by importing the module Flyte recorded for it at
submission and reading the task off it. Importing a marimo notebook runs only
its setup block and `@app.function` cells, so a workflow defined in a regular
cell runs on the notebook's own machine and nowhere else.
"""

from pathlib import Path

import pytest
from flyte._internal.resolvers.default import DefaultTaskResolver

import stargazer

# Where a hosted notebook bundles its runs' code from (`init_flyte`).
_BUNDLE_ROOT = Path(stargazer.__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("stargazer.notebooks.workflows.scrna_pipeline", "preprocess"),
        ("stargazer.notebooks.workflows.scrna_pipeline", "cluster_and_annotate"),
        ("stargazer.notebooks.templates.basic", "my_task"),
        ("stargazer.notebooks.templates.basic", "my_workflow"),
    ],
)
def test_pod_loads_the_task_submission_recorded(module, name):
    """The task a pod loads is the one whose loader args a submission records."""
    resolver = DefaultTaskResolver()
    task = resolver.load_task(["mod", module, "instance", name])

    assert resolver.loader_args(task, _BUNDLE_ROOT) == ["mod", module, "instance", name]
