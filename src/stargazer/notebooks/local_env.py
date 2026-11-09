"""
### Running a package task in its own environment on this machine.

Flyte's local mode runs a task in the calling process, so a notebook that ran a
package task on this machine would need the task's domain packages (scanpy,
gatk) in its own environment. `dispatch` runs a package task in its domain's
environment instead (`run_in_env`), the one its task image installs, so the
notebook installs none of them.

That environment is the PEP 723 header of the domain's `env.py` and the
`env.py.pixi.lock` beside it. Where the header lists this machine's platform
and pixi is installed, a hosted notebook pod included, pixi installs it as a
workspace under `STARGAZER_LOCAL/envs/<domain>` and runs the task there as a
subprocess. Elsewhere, where docker is installed, the task runs in its task
image, which installs the same lock. Either way the task imports the kernel's
own `stargazer` (`sdk_overlay`), so a checkout's edits run, and both sides
unpickle the same asset classes.

The inputs go in, and the output comes out, pickled in a call directory under
`STARGAZER_LOCAL`. A container sees the host's local scratch space, local store
and SQLite index at their own paths, and each input asset's directory
read-only, so the asset paths on both sides agree. Inside, this module's
`main` imports the task by module and name and runs it in Flyte's local mode.

A workflow's body runs in the caller instead, in Flyte's local mode, and
each package task it calls in its own environment (`routed`), so one
workflow can span gatk's and scRNA's.

Run there as `python -m stargazer.notebooks.local_env <call dir> <module>
<name>`. It never imports marimo, which a task environment doesn't have.

spec: [docs/architecture/notebook.md](../architecture/notebook.md)
"""

import asyncio
import contextlib
import importlib
import os
import pickle
import platform
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import flyte
from flyte._internal.controllers._local_controller import LocalController
from flyte._internal.imagebuild.docker_builder import DockerImageBuilder
from flyte._utils.pixi_script_parser import (
    effective_platforms,
    parse_pixi_script_file,
    platforms_for,
    render_pixi_manifest,
)

import stargazer
from stargazer.assets.asset import Asset
from stargazer.config import IMAGE_PLATFORM

# The modules whose tasks run in their domain's environment. A workflow's
# body runs in the caller instead, and its tasks each in their own.
_TASK_PACKAGES = ("stargazer.tasks.",)

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
# same image, or install the same environment, at once.
_build_lock = asyncio.Lock()

# Set while `dispatch` runs something on this machine, so the task
# environment's own local run, which calls the task in-process, isn't
# sent back to an environment.
_routing: ContextVar[bool] = ContextVar("stargazer_local_env_routing", default=False)

_TASKS = Path(stargazer.__file__).parent / "tasks"

# `sys.platform` and `platform.machine()` as conda's platform names.
_HOST_PLATFORMS = {
    ("darwin", "arm64"): "osx-arm64",
    ("darwin", "x86_64"): "osx-64",
    ("linux", "x86_64"): "linux-64",
    ("linux", "aarch64"): "linux-aarch64",
}


def _host_platform() -> str | None:
    """This machine's conda platform (`osx-arm64`, `linux-64`), or None."""
    return _HOST_PLATFORMS.get((sys.platform, platform.machine()))


def env_script(task: flyte.TaskTemplate) -> Path | None:
    """The `env.py` whose header is `task`'s environment, or None.

    The one whose module defines the `TaskEnvironment` `task` belongs to;
    `general/`'s tasks are on gatk's. None for a workflow, or a task from
    outside the package.
    """
    if not task.func.__module__.startswith(_TASK_PACKAGES) or task.parent_env is None:
        return None
    env = task.parent_env()
    for script in sorted(_TASKS.glob("*/env.py")):
        module = importlib.import_module(f"stargazer.tasks.{script.parent.name}.env")
        if any(value is env for value in vars(module).values()):
            return script
    return None


def executor(task: flyte.TaskTemplate) -> str | None:
    """Where `task` runs on this machine: `"pixi"`, `"docker"`, or None for this process.

    In pixi where its header lists this machine's platform and pixi is
    installed, else in its image where docker is.
    """
    script = env_script(task)
    if script is None:
        return None
    platforms = effective_platforms(
        parse_pixi_script_file(script), platforms_for(IMAGE_PLATFORM)
    )
    if _host_platform() in platforms and shutil.which("pixi"):
        return "pixi"
    if shutil.which("docker") and isinstance(task.image, flyte.Image):
        return "docker"
    return None


def workspace(script: Path) -> Path:
    """The pixi workspace for the header of `script`, under `STARGAZER_LOCAL/envs/<domain>`.

    The manifest Flyte's image builder renders from the header, and the lock
    beside it, as `cli/lock_envs.py` locks it, so the workspace installs what
    the task image does.
    """
    directory = Path(os.environ["STARGAZER_LOCAL"]) / "envs" / script.parent.name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "pixi.toml").write_text(
        render_pixi_manifest(
            parse_pixi_script_file(script), platforms_for(IMAGE_PLATFORM)
        )
    )
    shutil.copyfile(
        script.with_name(f"{script.name}.pixi.lock"), directory / "pixi.lock"
    )
    return directory


def sdk_overlay(call: Path) -> Path:
    """A directory under `call` holding only a link to the kernel's `stargazer`.

    It goes first on the environment's `PYTHONPATH`: the header installs the
    released SDK, and this puts the kernel's ahead of it, a checkout's source
    or the installed version alike.
    """
    overlay = call / "sdk"
    overlay.mkdir()
    (overlay / "stargazer").symlink_to(
        Path(stargazer.__file__).parent, target_is_directory=True
    )
    return overlay


async def _install(directory: Path) -> None:
    """Install the pixi workspace in `directory` as locked; quick when it's installed."""
    async with _build_lock:
        proc = await asyncio.create_subprocess_exec(
            "pixi",
            "install",
            "--manifest-path",
            str(directory / "pixi.toml"),
            # As locked, without checking the lock against the manifest: this
            # pixi can be newer than the one that wrote it (`cli/lock_envs.py`).
            "--frozen",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"pixi couldn't install {directory}:\n"
                f"{output.decode(errors='replace')[-4000:]}"
            )


async def _call(
    task: flyte.TaskTemplate,
    argv: list[str],
    where: str,
    call: Path,
    env: dict[str, str] | None = None,
) -> Any:
    """Run `argv`, which runs `task` on the inputs in `call`; return its output.

    A failed run raises `RuntimeError` naming the task and `where`, with the end
    of its output.
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    output, _ = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"{task.name} failed in {where} (exit {proc.returncode}):\n"
            f"{output.decode(errors='replace')[-4000:]}"
        )
    return pickle.loads((call / "output.pkl").read_bytes())


def _entrypoint(call: Path, task: flyte.TaskTemplate) -> list[str]:
    """The command that runs `task` on the inputs in `call` inside its environment."""
    return [
        "python",
        "-m",
        "stargazer.notebooks.local_env",
        str(call),
        task.func.__module__,
        task.func.__name__,
    ]


async def run_in_env(task: flyte.TaskTemplate, inputs: dict[str, Any]) -> Any:
    """Run `task` with `inputs` in its own environment, and return its output.

    In pixi or under docker, as `executor` picks, installing the environment or
    building the image first when this machine lacks it. A failed run raises
    `RuntimeError` with the end of the run's output.
    """
    local = Path(os.environ["STARGAZER_LOCAL"])
    local.mkdir(parents=True, exist_ok=True)
    call = Path(tempfile.mkdtemp(prefix="env-run-", dir=local))
    try:
        (call / "inputs.pkl").write_bytes(pickle.dumps(inputs))
        if executor(task) == "pixi":
            return await _run_in_pixi(task, call)
        return await _run_in_image(task, inputs, call)
    finally:
        shutil.rmtree(call, ignore_errors=True)


@contextlib.contextmanager
def routed() -> Iterator[None]:
    """Within it, a local run sends each package task it calls to its environment.

    `dispatch` runs a workflow's body here in Flyte's local mode, whose
    controller would run the body's tasks in this process too.
    """
    token = _routing.set(True)
    try:
        yield
    finally:
        _routing.reset(token)


_submit = LocalController.submit


async def _submit_in_env(
    self: LocalController, task: flyte.TaskTemplate, *args: Any, **kwargs: Any
) -> Any:
    """`LocalController.submit`, sending a package task to its environment when routed."""
    if _routing.get() and executor(task) is not None:
        inputs = dict(zip(task.native_interface.inputs, args, strict=False))
        return await run_in_env(task, {**inputs, **kwargs})
    return await _submit(self, task, *args, **kwargs)


# Flyte's local controller has no hook for where a task runs. Private API,
# so an SDK upgrade can move it.
LocalController.submit = _submit_in_env


async def _run_in_pixi(task: flyte.TaskTemplate, call: Path) -> Any:
    """Run `task` on the inputs in `call` as a subprocess in its pixi environment."""
    directory = workspace(env_script(task))
    await _install(directory)
    # The kernel's own variables, storage settings and secrets included, as a
    # task in this process would see them.
    env = {**os.environ, "PYTHONPATH": str(sdk_overlay(call))}
    argv = [
        "pixi",
        "run",
        "--manifest-path",
        str(directory / "pixi.toml"),
        "--frozen",
        *_entrypoint(call, task),
    ]
    return await _call(task, argv, f"its {directory.name} environment", call, env)


async def _run_in_image(
    task: flyte.TaskTemplate, inputs: dict[str, Any], call: Path
) -> Any:
    """Run `task` on the inputs in `call` in its image under docker."""
    # Docker would make a missing mount source itself, owned by root.
    for directory in _writable_dirs():
        directory.mkdir(parents=True, exist_ok=True)
    mounts = _mounts(inputs)
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
    argv += [uri, *_entrypoint(call, task)]
    return await _call(task, argv, uri, call)


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
