# Where Your Code Runs

1. **An environment is a header.** A domain's is the header of `tasks/<domain>/env.py`, locked and published as an image with each release. A notebook's is the header at its top, which marimo writes as you import.
2. **On this machine, everything runs in your notebook's kernel.** So your header lists what you run here: what your cells import, and the packages and tools of any SDK task you run on this machine.
3. **On the cluster, each task runs in its environment's image.** An SDK task runs in its domain's image, and your notebook's own tasks in an image built from your notebook's header.

So a header is the one place a task's packages are listed, and the image a cluster runs is built from it.

## Your notebook's header

A notebook that sends the SDK's scRNA-seq tasks to the cluster and plots what comes back lists only what its cells import:

```python
# /// script
# requires-python = ">=3.14"
# dependencies = ["marimo", "stargazer-bio", "matplotlib"]
#
# [tool.pixi.dependencies]
# python = "3.14.*"
# ///
```

To run those tasks on this machine too, add what they import, here `"scanpy"`, with `"igraph"` for Leiden clustering. The header of the domain's `env.py` (`src/stargazer/tasks/scrna/env.py`) is the full list. A command-line tool goes under `[tool.pixi.dependencies]`, with bioconda among the channels ([Getting Started](../getting-started.md#packages-and-tools) shows one): the alignment and GATK tasks call `gatk4`, `samtools`, `bwa` and `bwa-mem2`.

## On this machine

The switch from `run_location()` decides where `dispatch` runs a task (the Execution tutorial walks through both). *On this machine* runs the task in your kernel, and a workflow with every task it calls. It's the place to try a step on a small input and look at the result in the next cell.

A task whose package or tool your header doesn't list fails where it reaches for it, with an error naming what's missing: `No module named 'scanpy'`, or `No such file or directory: 'samtools'`. Add it to the header, or send that run to the cluster, where the task's own image has it.

A hosted notebook works the same way: *On this machine* is its pod.

## On the cluster

Every task runs in a pod of its own, on its environment's image. An SDK task's image is built from its domain's header and lock. Your notebook's own tasks run on an image built from your notebook's header when their environment comes from `notebook_task_environment(__file__, ...)`, as the template's does:

```python
my_env = notebook_task_environment(
    __file__,
    "my-tasks",
    resources=flyte.Resources(cpu=1, memory="512Mi"),
)
```

Either way, the SDK your run was submitted with goes on top: your checkout's source, or the release you have installed.

## At your own risk

These work, but the guarantees above don't cover them:

- **Any other image** on your notebook's own `TaskEnvironment`, such as `flyte.Image.from_debian_base(...)` with layers added, or `flyte.Image.from_base`.
- **An unlocked notebook header.** Its cluster image can resolve differently from one build to the next, so the header alone doesn't pin what a run gets.
- **An SDK task run on this machine** gets the versions your header resolved, not the ones its domain's lock pins. The cluster's run is the reproducible one.
- **A tool with no build for your machine.** Run its tasks on the cluster, or open the notebook in the Stargazer image.
