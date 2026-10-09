#!/usr/bin/env python3
"""
Run the `tools` tier: the tests that need `gatk_env`'s command-line tools.

Those tools (gatk, bwa, bwa-mem2, samtools) are installed in `gatk_env`'s
image, not on a developer's machine, so the tests marked `tools` run in that
image. This builds it into the local docker store (no registry) as a task pod
gets it, x86_64 like Union, and runs pytest in it against the stargazer the
image installs. Only the tests and the pytest configuration are mounted, read
only, so a source change builds the image again first; the layers before the
project's own come from cache. On Apple silicon the container runs under
emulation. Needs docker; not the devbox.

Usage:
    uv run --all-extras python cli/docker_task_tests.py [paths or -k EXPR]

The arguments select tests as they would for pytest, among those marked
`tools`; with none, it runs every such test under `tests/`. Exits with
pytest's exit code.
"""

import asyncio
import subprocess
import sys

from flyte._internal.imagebuild.docker_builder import DockerImageBuilder

from stargazer.config import PROJECT_ROOT, gatk_env

# All the container sees of the checkout: the tests, and the pytest settings
# (markers, asyncio mode) in pyproject.toml.
MOUNTS = ("tests", "pyproject.toml")


def build_image() -> str:
    """Build `gatk_env`'s image into the local docker store; return its name.

    Skipped when docker already holds it for the image's platform. The name
    carries a hash of the recipe and the project, not the platform, so an
    image built for another platform can hold the same name.
    """
    image = gatk_env.image
    inspect = ["docker", "image", "inspect", "--platform", image.platform[0], image.uri]
    if subprocess.run(inspect, capture_output=True, check=False).returncode != 0:
        # `flyte.build()` refuses a local build it can't push to a registry;
        # the builder's own `push=False` loads it into docker instead. Private
        # API, so an SDK upgrade can move it.
        asyncio.run(DockerImageBuilder()._build_image(image, push=False))
    return image.uri


def tool_tests(args: list[str]) -> list[str]:
    """Node IDs of the `tools` tests `args` select, collected in this venv.

    Collected here rather than in the image, which carries `gatk_env`'s
    dependencies only and can't import every test module (the app tier's,
    the scRNA ones) just to find which are marked.
    """
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "tools"]
        + (args or ["tests"]),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,  # an empty or failed collection is reported below
    )
    ids = [line for line in collected.stdout.splitlines() if "::" in line]
    if not ids:
        raise SystemExit(
            f"No tools tests selected:\n{collected.stdout}{collected.stderr}"
        )
    return ids


def main(args: list[str]) -> int:
    """Build the image, run the `tools` tests in it, return pytest's exit code."""
    tests = tool_tests(args)
    image = build_image()
    print(f"image: {image}", flush=True)
    mounts = [
        arg
        for name in MOUNTS
        for arg in ("-v", f"{PROJECT_ROOT / name}:/work/{name}:ro")
    ]
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--platform",
            gatk_env.image.platform[0],
            *mounts,
            "-w",
            "/work",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            image,
            "python",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            # Replaces the default `-m` in pyproject.toml, which excludes them.
            "-m",
            "tools",
            *tests,
        ],
        check=False,  # pytest's exit code is the result
    ).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
