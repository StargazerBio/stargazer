"""Tests for the task registry."""

from stargazer.registry import TaskRegistry


def test_discovery_finds_all_tasks():
    """Registry discovers all tasks from stargazer.tasks."""
    reg = TaskRegistry()
    task_names = {t.name for t in reg.list_tasks(category="task")}

    expected_tasks = {
        "samtools_faidx",
        "create_sequence_dictionary",
        "bwa_index",
        "bwa_mem",
        "bwa_mem2_index",
        "bwa_mem2_mem",
        "sort_sam",
        "mark_duplicates",
        "merge_bam_alignment",
        "base_recalibrator",
        "apply_bqsr",
        "haplotype_caller",
        "combine_gvcfs",
        "genomics_db_import",
        "joint_call_gvcfs",
        "variant_recalibrator",
        "apply_vqsr",
        "index_feature_file",
    }
    assert expected_tasks == task_names


def test_discovery_finds_all_workflows():
    """Registry discovers all workflows from both workflow modules."""
    reg = TaskRegistry()
    wf_names = {t.name for t in reg.list_tasks(category="workflow")}

    expected_workflows = {
        # gatk_data_preprocessing
        "prepare_reference",
        "preprocess_sample",
        # germline_short_variant_discovery
        "germline_short_variant_discovery",
        # scrna_clustering
        "scrna_clustering_pipeline",
    }
    assert expected_workflows == wf_names


def test_duplicate_prepare_reference_not_duplicated():
    """prepare_reference exists in both workflow modules but is registered once."""
    reg = TaskRegistry()
    matches = [t for t in reg.list_tasks() if t.name == "prepare_reference"]
    assert len(matches) == 1
    assert matches[0].category == "workflow"


def test_to_catalog_structure():
    """to_catalog returns correct structure with types, params, outputs."""
    reg = TaskRegistry()
    catalog = reg.to_catalog()

    assert isinstance(catalog, list)
    assert len(catalog) > 0

    # Find bwa_mem in catalog
    bwa_mem_entry = next(e for e in catalog if e["name"] == "bwa_mem")
    assert bwa_mem_entry["category"] == "task"
    assert bwa_mem_entry["description"]  # non-empty

    # Check params
    param_names = {p["name"] for p in bwa_mem_entry["params"]}
    assert param_names == {"r1", "r2", "ref", "read_group"}

    # r1 is required
    r1_param = next(p for p in bwa_mem_entry["params"] if p["name"] == "r1")
    assert r1_param["required"] is True
    assert "R1" in r1_param["type"]

    # read_group is optional
    rg_param = next(p for p in bwa_mem_entry["params"] if p["name"] == "read_group")
    assert rg_param["required"] is False

    # Check outputs
    assert len(bwa_mem_entry["outputs"]) == 1
    assert bwa_mem_entry["outputs"][0]["name"] == "o0"
    assert "Alignment" in bwa_mem_entry["outputs"][0]["type"]


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
