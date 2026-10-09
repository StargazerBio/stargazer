#!/usr/bin/env python3
"""
Run the tasks tier: tests/tasks, each domain's tests in its tasks' image.

A task test runs where the task does, in its TaskEnvironment's image
(`IMAGES`), so it tests what a pod gets, and the command-line tools the gatk
and alignment tasks wrap (gatk, bwa, bwa-mem2, samtools) never have to be on
a developer's machine. This builds each image into the local docker store (no
registry) as a task pod gets it, x86_64 like Union, and runs pytest in it
against the stargazer the image installs. Only the tests and the pytest
configuration are mounted, read only, so a source change builds the images
again first; the layers before the project's own come from cache. On Apple
silicon the containers run under emulation. Needs docker; not the devbox.

Usage:
    uv run --all-extras python cli/docker_task_tests.py [paths or -k EXPR]

The arguments select tests under tests/tasks as they would for pytest; with
none, it runs them all. Exits 0 when every image's run passes, otherwise with
the first failing run's pytest exit code.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

import flyte
from flyte._internal.imagebuild.docker_builder import DockerImageBuilder

from stargazer.config import PROJECT_ROOT, gatk_env, scrna_env

# The image each tests/tasks/<domain> runs in: the one its tasks run in.
IMAGES = {
    "gatk": gatk_env.image,
    "general": gatk_env.image,
    "scrna": scrna_env.image,
}

# All the container sees of the checkout: the tests, and the pytest settings
# (markers, asyncio mode) in pyproject.toml.
MOUNTS = ("tests", "pyproject.toml")


def build_image(image: flyte.Image) -> str:
    """Build `image` into the local docker store; return its name.

    Skipped when docker already holds it for the image's platform. The name
    carries a hash of the recipe and the project, not the platform, so an
    image built for another platform can hold the same name.
    """
    inspect = ["docker", "image", "inspect", "--platform", image.platform[0], image.uri]
    if subprocess.run(inspect, capture_output=True, check=False).returncode != 0:
        # `flyte.build()` refuses a local build it can't push to a registry;
        # the builder's own `push=False` loads it into docker instead. Private
        # API, so an SDK upgrade can move it.
        asyncio.run(DockerImageBuilder()._build_image(image, push=False))
    return image.uri


def task_tests(args: list[str]) -> dict[str, list[str]]:
    """The node IDs `args` select under tests/tasks, by domain.

    Collected in this venv rather than in an image, which can't import
    another domain's test modules.
    """
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "tasks"]
        + (args or ["tests/tasks"]),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,  # an empty or failed collection is reported below
    )
    by_domain: dict[str, list[str]] = {}
    for line in collected.stdout.splitlines():
        if "::" in line:
            domain = Path(line.split("::")[0]).parts[2]
            by_domain.setdefault(domain, []).append(line)
    if not by_domain:
        raise SystemExit(
            f"No task tests selected:\n{collected.stdout}{collected.stderr}"
        )
    return by_domain


def run_in(image: flyte.Image, tests: list[str]) -> int:
    """Build `image`, run `tests` in it, return pytest's exit code."""
    uri = build_image(image)
    print(f"image: {uri}", flush=True)
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
            image.platform[0],
            *mounts,
            "-w",
            "/work",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            uri,
            "python",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            # Replaces the default `-m unit` in pyproject.toml.
            "-m",
            "tasks",
            *tests,
        ],
        check=False,  # pytest's exit code is the result
    ).returncode


def main(args: list[str]) -> int:
    """Run the selected task tests, each domain's in its image."""
    # Flyte reads .dockerignore from the root_dir it was initialized with.
    # Without one, the build context is the whole checkout, scratch/ and
    # .venv included.
    flyte.init(root_dir=PROJECT_ROOT)
    by_image: dict[str, tuple[flyte.Image, list[str]]] = {}
    for domain, tests in task_tests(args).items():
        if domain not in IMAGES:
            raise SystemExit(
                f"tests/tasks/{domain} has no image: add it to IMAGES in cli/docker_task_tests.py"
            )
        image = IMAGES[domain]
        by_image.setdefault(image.uri, (image, []))[1].extend(tests)
    codes = [run_in(image, tests) for image, tests in by_image.values()]
    return next((code for code in codes if code), 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
