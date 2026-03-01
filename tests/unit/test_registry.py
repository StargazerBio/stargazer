"""Tests for the task registry."""

from stargazer.registry import TaskRegistry


def test_discovery_finds_all_tasks():
    """Registry discovers all tasks from stargazer.tasks."""
    reg = TaskRegistry()
    task_names = {t.name for t in reg.list_tasks(category="task")}

    expected_tasks = {
        "hydrate",
        "samtools_faidx",
        "create_sequence_dictionary",
        "bwa_index",
        "bwa_mem",
        "sort_sam",
        "mark_duplicates",
        "merge_bam_alignment",
        "base_recalibrator",
        "apply_bqsr",
        "analyze_covariates",
        "genotype_gvcf",
        "combine_gvcfs",
        "genomics_db_import",
        "variant_recalibrator",
        "apply_vqsr",
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
        "preprocess_cohort",
        "apply_bqsr_to_alignment",
        # germline_short_variant_discovery
        "align_sample",
        "call_variants_gvcf",
        "germline_single_sample",
        "germline_cohort",
        "germline_from_gvcfs",
        "germline_cohort_with_vqsr",
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
    assert param_names == {"reads", "ref", "read_group"}

    # reads is required
    reads_param = next(p for p in bwa_mem_entry["params"] if p["name"] == "reads")
    assert reads_param["required"] is True
    assert "Reads" in reads_param["type"]

    # read_group is optional
    rg_param = next(p for p in bwa_mem_entry["params"] if p["name"] == "read_group")
    assert rg_param["required"] is False

    # Check outputs
    assert len(bwa_mem_entry["outputs"]) == 1
    assert bwa_mem_entry["outputs"][0]["name"] == "o0"
    assert "Alignment" in bwa_mem_entry["outputs"][0]["type"]


def test_multi_output_task():
    """Tasks with tuple returns have multiple outputs (o0, o1, ...)."""
    reg = TaskRegistry()
    info = reg.get("variant_recalibrator")
    assert info is not None
    assert len(info.outputs) == 2
    assert info.outputs[0].name == "o0"
    assert info.outputs[1].name == "o1"


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
    info = reg.get("hydrate")
    assert info is not None
    assert hasattr(info.task_obj, "func")
    assert callable(info.task_obj.func)
