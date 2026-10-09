#!/usr/bin/env python3
"""
Run the GATK and alignment task tests locally, in `gatk_env`'s image.

Their tools (`gatk`, `bwa`, `samtools`) are installed in that image, not on a
developer's PATH, so outside it those tests skip. This builds the image into
the local docker store (no registry) and runs pytest in it, with the repo mounted and its `src/` on `PYTHONPATH`. A
source change needs no rebuild; a change to the image recipe or the lockfile
does, and the build is cached otherwise. The image already carries pytest: uv
installs the `dev` group by default.

It always builds and runs x86_64, the architecture Union runs: GATK's
GenomicsDB, which joint calling uses, has no arm64 build. On Apple silicon
the container runs under emulation.

The container checks the tools are on PATH before pytest starts, so the tests
can't pass by skipping. Needs docker; not the devbox.

Usage:
    uv run python cli/docker_task_tests.py [pytest args...]

With no arguments it runs `tests/tasks/gatk` and `tests/tasks/general`.
Exits with pytest's exit code.
"""

import asyncio
import subprocess
import sys

from flyte._internal.imagebuild.docker_builder import DockerImageBuilder

from stargazer.config import PROJECT_ROOT, gatk_env

DEFAULT_ARGS = ["tests/tasks/gatk", "tests/tasks/general", "-rs"]

# Every tool the default tests skip without.
TOOLS = ("gatk", "bwa", "samtools")

PLATFORM = "linux/amd64"

# Run in the container: fail on a missing tool, then hand over to pytest.
_ENTRY = (
    'for t in $TOOLS; do command -v "$t" >/dev/null '
    '|| { echo "Not on the image\'s PATH: $t" >&2; exit 1; }; done; '
    'exec python -m pytest -p no:cacheprovider "$@"'
)


def build_image() -> str:
    """Build `gatk_env`'s image into the local docker store; return its name.

    Skipped when docker already holds it for x86_64: the name carries a hash
    of the recipe, not the platform, and loading a multi-GB image costs more
    than the cached build.
    """
    image = gatk_env.image.clone(platform=(PLATFORM,))
    inspect = ["docker", "image", "inspect", "--platform", PLATFORM, image.uri]
    if subprocess.run(inspect, capture_output=True, check=False).returncode != 0:
        # `flyte.build()` refuses a local build it can't push to a registry;
        # the builder's own `push=False` loads it into docker instead. Private
        # API, so an SDK upgrade can move it.
        asyncio.run(DockerImageBuilder()._build_image(image, push=False))
    return image.uri


def main(args: list[str]) -> int:
    """Build the image, run pytest in it, return pytest's exit code."""
    image = build_image()
    print(f"image: {image}", flush=True)
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--platform",
            PLATFORM,
            "-v",
            f"{PROJECT_ROOT}:/work",
            "-w",
            "/work",
            "-e",
            "PYTHONPATH=/work/src",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            f"TOOLS={' '.join(TOOLS)}",
            image,
            "sh",
            "-c",
            _ENTRY,
            "sh",
            *(args or DEFAULT_ARGS),
        ],
        check=False,  # pytest's exit code is the result
    ).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
