"""
### Running a package task in its own image on this machine.

Flyte's local mode runs a task in the calling process, so a notebook that runs
a package task on this machine would need the task's domain packages (scanpy,
gatk) in its own environment. Where docker is on the PATH, `dispatch` runs a
package task in its task image instead (`run_in_image`), the same environment
a cluster run gets, so the notebook installs none of them. A hosted notebook
pod has no docker, so there the task stays in the kernel.

The container sees the host's local scratch space, local store and SQLite
index at their own paths, and each input asset's directory read-only, so the
asset paths on both sides agree. The inputs go in, and the output comes out,
pickled in a call directory under `STARGAZER_LOCAL`. Inside, this module's
`main` imports the task by module and name and runs it in Flyte's local mode,
so a workflow's child tasks run in the same container.

Run in an image as `python -m stargazer.notebooks.local_image <call dir>
<module> <name>`. It never imports marimo, which a task image doesn't have.

spec: [docs/architecture/notebook.md](../architecture/notebook.md)
"""

import asyncio
import importlib
import os
import pickle
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import flyte
from flyte._internal.imagebuild.docker_builder import DockerImageBuilder

from stargazer.assets.asset import Asset

# The modules a task image installs, which the container can import a task from.
_PACKAGES = ("stargazer.tasks.", "stargazer.workflows.")

# Passed by name (`-e NAME`), so a secret's value never shows in the command
# line; one the kernel doesn't set is left out.
_PASSED_VARS = (
    "STARGAZER_LOCAL",
    "STARGAZER_STORE_ROOT",
    "STARGAZER_INDEX_URL",
    "PINATA_GATEWAY",
    "PINATA_JWT",
    "STARGAZER_OWNER",
)

# Samples dispatched together with `asyncio.gather` would otherwise build the
# same image at once.
_build_lock = asyncio.Lock()


def runs_in_image(task: flyte.TaskTemplate) -> bool:
    """Whether `task` runs in its image on this machine.

    It does where docker is on the PATH and the image installs the task's
    module.
    """
    return (
        shutil.which("docker") is not None
        and task.func.__module__.startswith(_PACKAGES)
        and isinstance(task.image, flyte.Image)
    )


async def build_image(image: flyte.Image) -> str:
    """Build `image` into the local docker store; return its name.

    Skipped when docker already holds it for the image's platform. The name
    carries a hash of the recipe and the project, not the platform, so an
    image built for another platform can hold the same name.
    """
    async with _build_lock:
        inspect = await asyncio.create_subprocess_exec(
            *("docker", "image", "inspect", "--platform", image.platform[0], image.uri),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if await inspect.wait() != 0:
            # `flyte.build()` refuses a local build it can't push to a registry;
            # the builder's own `push=False` loads it into docker instead. Private
            # API, so an SDK upgrade can move it.
            await DockerImageBuilder()._build_image(image, push=False)
    return image.uri


def _local_dir(value: str) -> Path | None:
    """`value` as a local path, or None for a URI (`s3://`, `postgresql://`, `dsql://`)."""
    if "://" in value:
        return None
    return Path(value)


def _input_files(value: Any) -> list[Path]:
    """The local files of the assets in `value`, in lists, tuples and dict values too."""
    if isinstance(value, Asset):
        if value.path is not None:
            local = _local_dir(value.path.path)
            return [local] if local is not None else []
        return []
    if isinstance(value, (list, tuple)):
        return [path for item in value for path in _input_files(item)]
    if isinstance(value, dict):
        return [path for item in value.values() for path in _input_files(item)]
    return []


def _writable_dirs() -> list[Path]:
    """This machine's scratch space, and its store and index when they're local."""
    writable = [Path(os.environ["STARGAZER_LOCAL"])]
    store = _local_dir(os.environ["STARGAZER_STORE_ROOT"])
    if store is not None:
        writable.append(store)
    index = _local_dir(os.environ["STARGAZER_INDEX_URL"])
    if index is not None:
        writable.append(index.parent)
    return writable


def _mounts(inputs: dict[str, Any]) -> list[str]:
    """The `-v` values that show the container this machine's storage and `inputs`' files.

    Each at its own path: storage writable, an existing input file's directory
    read-only unless storage already covers it.
    """
    writable = _writable_dirs()
    readonly: list[Path] = []
    for path in _input_files(inputs):
        directory = path.parent
        if directory in readonly:
            continue
        if any(directory.is_relative_to(w) for w in writable):
            continue
        # The task's own error names a missing file better than docker's.
        if not directory.is_dir():
            continue
        readonly.append(directory)

    return [f"{d}:{d}" for d in writable] + [f"{d}:{d}:ro" for d in readonly]


async def run_in_image(task: flyte.TaskTemplate, inputs: dict[str, Any]) -> Any:
    """Run `task` with `inputs` in its image under docker, and return its output.

    Builds the image first when docker doesn't hold it. A failed run raises
    `RuntimeError` with the end of the container's output.
    """
    # Docker would make a missing mount source itself, owned by root.
    for directory in _writable_dirs():
        directory.mkdir(parents=True, exist_ok=True)
    mounts = _mounts(inputs)
    call = Path(
        tempfile.mkdtemp(prefix="image-run-", dir=os.environ["STARGAZER_LOCAL"])
    )
    try:
        (call / "inputs.pkl").write_bytes(pickle.dumps(inputs))
        uri = await build_image(task.image)
        argv = [
            "docker",
            "run",
            "--rm",
            "--platform",
            task.image.platform[0],
            # The files it writes are the host user's; that user has no home in
            # the image.
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-e",
            "HOME=/tmp",
            "-w",
            "/tmp",
        ]
        for mount in mounts:
            argv += ["-v", mount]
        for name in _PASSED_VARS:
            if name in os.environ:
                argv += ["-e", name]
        argv += [
            uri,
            "python",
            "-m",
            "stargazer.notebooks.local_image",
            str(call),
            task.func.__module__,
            task.func.__name__,
        ]
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"{task.name} failed in {uri} (exit {proc.returncode}):\n"
                f"{output.decode(errors='replace')[-4000:]}"
            )
        return pickle.loads((call / "output.pkl").read_bytes())
    finally:
        shutil.rmtree(call, ignore_errors=True)


async def _run(call: Path, module: str, name: str) -> None:
    """Run the task `module.name` on the inputs pickled in `call`, and pickle its output there.

    In Flyte's local mode, so a workflow's child tasks run in this container too.
    """
    task = getattr(importlib.import_module(module), name)
    inputs = pickle.loads((call / "inputs.pkl").read_bytes())
    flyte.init()
    run = await flyte.with_runcontext(mode="local").run.aio(task, **inputs)
    await run.wait.aio()
    output = (await run.outputs.aio())[0]
    (call / "output.pkl").write_bytes(pickle.dumps(output))


def main(argv: list[str]) -> None:
    """The container's entrypoint: `<call dir> <module> <name>`."""
    call, module, name = argv
    asyncio.run(_run(Path(call), module, name))


if __name__ == "__main__":
    main(sys.argv[1:])
