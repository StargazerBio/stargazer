"""
### The images Stargazer's tasks run on.

A domain's tasks build from its `env.py`'s header (`task_image()`), and a
notebook's own tasks from the notebook's header (`notebook_image()`). Both put
the SDK on top: a checkout's source, or the installed release from PyPI.

Where images are pushed is Flyte's own setting, `FLYTE_IMAGE_REGISTRY`. Flyte
fixes an image's registry when the image is defined, so the environments take
it at import, not from the config a later init reads.

This module imports nothing of Stargazer's, so `stargazer.config` can ask it
whether the package runs from a checkout. `notebook_image()` writes under
`STARGAZER_LOCAL`, whose default `stargazer.config` sets: importing this
module runs the package root, which loads `stargazer.config`, so the default
is in place before `notebook_image()` can be called.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import hashlib
import os
import re
from importlib.metadata import version
from pathlib import Path

import flyte

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Every Stargazer image is built for x86_64 only, the architecture Union runs.
# GATK's GenomicsDB ships an x86_64-only native library, so an arm64 build
# can't joint-call; on an Apple-silicon devbox these pods run emulated.
IMAGE_PLATFORM = ("linux/amd64",)


def _checkout() -> bool:
    """Whether the package runs from a checkout, whose source its images install.

    Installed from PyPI, `PROJECT_ROOT` is the environment's `lib/python3.x`,
    which holds no `pyproject.toml`.
    """
    return (PROJECT_ROOT / "pyproject.toml").is_file()


def _with_sdk(image: flyte.Image) -> flyte.Image:
    """`image` with the SDK this process runs installed on top.

    A task pod resolves the tasks it calls as installed modules
    (`stargazer.tasks…`), so the package must be the submitter's. From a
    checkout that's its source, a layer of its own, so a source change
    rebuilds only it; the checkout's .dockerignore keeps docs, tests, git
    history and pixi's environments out of it, and out of every other folder
    the image copies. It's named here because Flyte otherwise reads the one in
    `flyte.init`'s root, which is the cwd, or `src/` in a notebook pod
    (`init_flyte`). uv installs into the pixi environment, which the layer
    below made `VIRTUAL_ENV`, with any core dependency the checkout has gained
    since the release the layer below installed. An installed package has no
    source to copy: its own release goes on top, from PyPI.
    """
    if not _checkout():
        return image.with_pip_packages(f"stargazer-bio=={version('stargazer-bio')}")
    return (
        image.with_dockerignore(PROJECT_ROOT / ".dockerignore")
        .with_source_folder(PROJECT_ROOT, "/opt/stargazer")
        .with_commands(["uv pip install --no-cache /opt/stargazer"])
    )


def task_image(env: str | Path) -> flyte.Image:
    """A domain's task image, `stargazer-<domain>`: its `env.py`'s header, then the SDK.

    `env` is the domain's `env.py` (its `__file__`), whose PEP 723 header lists
    the environment's conda and PyPI packages, the released SDK among them,
    locked in the `env.py.pixi.lock` beside it (`cli/lock_envs.py`). Flyte
    renders the header as a pixi workspace and installs it from the header and
    lock alone, so that layer (Python, the tools, every dependency) is cached
    until either changes, and pixi's environment is the pod's Python. The SDK
    goes on top (`_with_sdk()`): a checkout's source, or the installed
    release. The header and lock ship in the package, so an installed package
    builds its images the same way, with whichever builder its Flyte config
    picks.
    """
    env = Path(env)
    name = f"stargazer-{env.parent.name}"
    image = flyte.Image.from_pixi_script(env, name=name, platform=IMAGE_PLATFORM)
    return _with_sdk(image)


# The PEP 723 block, as Flyte's pixi script parser reads it.
_SCRIPT_BLOCK = re.compile(r"(?m)^# /// script\s*$\s(?:^#(?: .*)?$\s)*?^# ///\s*$")


def _header_without_sdk_source(notebook: Path) -> str:
    """`notebook`'s PEP 723 block, less its `[tool.pixi.pypi-dependencies]` SDK line."""
    block = _SCRIPT_BLOCK.search(notebook.read_text()).group(0)
    table = ""
    kept = []
    for line in block.splitlines():
        text = line.removeprefix("#").strip()
        if text.startswith("["):
            table = text
        if table == "[tool.pixi.pypi-dependencies]" and text.startswith(
            "stargazer-bio"
        ):
            continue
        kept.append(line)
    return "\n".join(kept) + "\n"


def notebook_image(notebook: str | Path, name: str) -> flyte.Image:
    """The image a notebook's own tasks run on: its header, then the SDK on top.

    `notebook` is the notebook's file (its `__file__`), whose PEP 723 header
    lists what its cells and tasks use. The header's `stargazer-bio` source in
    `[tool.pixi.pypi-dependencies]` is the SDK a notebook pod holds
    (`/stargazer`), which no image build has, so the build reads a copy of the
    header without it, under `STARGAZER_LOCAL`, and `stargazer-bio` installs
    from PyPI. Flyte names the image by the manifest the header renders to, so
    the kernel and a cluster pod, each with its own copy, name the same image.
    The SDK then goes on top (`_with_sdk()`). marimo writes no lock for a
    header, so the image resolves its packages anew whenever it's built.
    """
    header = _header_without_sdk_source(Path(notebook))
    digest = hashlib.sha256(header.encode()).hexdigest()[:16]
    script = (
        Path(os.environ["STARGAZER_LOCAL"])
        / "notebook-headers"
        / digest
        / Path(notebook).name
    )
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(header)
    image = flyte.Image.from_pixi_script(script, name=name, platform=IMAGE_PLATFORM)
    return _with_sdk(image)
