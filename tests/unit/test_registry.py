"""Tests for the task registry."""

import importlib
import pkgutil
import types
from typing import Optional, Union

import pytest

import stargazer.tasks
import stargazer.workflows
from stargazer.registry import TaskRegistry, _type_name


def _defined_task_names(package: types.ModuleType) -> set[str]:
    """Short names of the tasks defined in every module under `package`.

    A task a module only imports is left to the module that defines it.
    """
    names = set()
    for info in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
        module = importlib.import_module(info.name)
        names |= {
            obj.short_name
            for obj in vars(module).values()
            if hasattr(obj, "func") and obj.func.__module__ == info.name
        }
    return names


def test_discovery_finds_every_defined_task():
    """Every task defined under stargazer.tasks is registered, so none goes unexported."""
    reg = TaskRegistry()
    task_names = {t.name for t in reg.list_tasks(category="task")}

    defined = _defined_task_names(stargazer.tasks)
    assert {"bwa_mem", "qc_filter"} <= defined
    assert defined == task_names


def test_discovery_finds_every_defined_workflow():
    """Every workflow defined under stargazer.workflows is registered, so none goes unexported."""
    reg = TaskRegistry()
    wf_names = {t.name for t in reg.list_tasks(category="workflow")}

    defined = _defined_task_names(stargazer.workflows)
    assert {"prepare_reference", "scrna_clustering_pipeline"} <= defined
    assert defined == wf_names


def test_to_catalog_structure():
    """to_catalog returns correct structure with types, params, outputs."""
    reg = TaskRegistry()
    catalog = reg.to_catalog()

    assert isinstance(catalog, list)
    assert len(catalog) > 0

    bwa_mem_entry = next(e for e in catalog if e["name"] == "bwa_mem")
    assert bwa_mem_entry["category"] == "task"
    assert bwa_mem_entry["description"]  # non-empty

    param_names = {p["name"] for p in bwa_mem_entry["params"]}
    assert param_names == {"r1", "r2", "ref", "read_group"}

    r1_param = next(p for p in bwa_mem_entry["params"] if p["name"] == "r1")
    assert r1_param["required"] is True
    assert "R1" in r1_param["type"]

    rg_param = next(p for p in bwa_mem_entry["params"] if p["name"] == "read_group")
    assert rg_param["required"] is False
    assert rg_param["type"] == "dict[str, str] | NoneType"

    assert len(bwa_mem_entry["outputs"]) == 1
    assert bwa_mem_entry["outputs"][0]["name"] == "o0"
    assert "Alignment" in bwa_mem_entry["outputs"][0]["type"]


@pytest.mark.parametrize(
    "hint",
    # The old spellings are the point: they build a different object on 3.13.
    [int | None, Optional[int], Union[int, None]],  # noqa: UP007, UP045
    ids=["pipe", "Optional", "Union"],
)
def test_type_name_renders_optional_as_pipe_union(hint):
    """Every spelling of an optional renders the same way on every Python.

    3.14 gives `int | None` a `typing.Union` origin, which 3.13 only gives
    `Optional`/`Union`, so the catalog would change with the interpreter.
    """
    assert _type_name(hint) == "int | NoneType"


def test_get_returns_none_for_unknown():
    """get() returns None for unregistered task names."""
    reg = TaskRegistry()
    assert reg.get("nonexistent_task") is None


def test_list_tasks_no_filter():
    """list_tasks with no category returns all tasks and workflows."""
    reg = TaskRegistry()
    all_tasks = reg.list_tasks()
    tasks_only = reg.list_tasks(category="task")
    workflows_only = reg.list_tasks(category="workflow")
    assert len(all_tasks) == len(tasks_only) + len(workflows_only)


def test_task_info_has_task_obj():
    """TaskInfo stores the original Flyte task object."""
    reg = TaskRegistry()
    info = reg.get("bwa_mem")
    assert info is not None
    assert hasattr(info.task_obj, "func")
    assert callable(info.task_obj.func)
