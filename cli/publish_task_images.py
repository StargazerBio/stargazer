#!/usr/bin/env python3
"""
Publish the task images for this checkout's SDK version.

Builds the gatk and scrna images from their recipes in `stargazer.config`,
the same ones a checkout's runs build, and pushes each as
`ghcr.io/stargazerbio/<image>:<version>`: the image an installed package's
`gatk_env` and `scrna_env` run (`stargazer.config.task_image`). CI runs it
(.github/workflows/task-images.yml), signed in to GHCR; a run from a
maintainer's machine needs `docker login ghcr.io` first. The images are
x86_64, so on Apple silicon the gatk build runs under emulation and is slow.

Usage:
    uv run python cli/publish_task_images.py [--expect-version X.Y.Z]

`--expect-version` refuses to publish unless the checkout's version is
X.Y.Z, so a release tag can't publish images under another version.
"""

import argparse
import asyncio
import subprocess
from importlib import metadata

from flyte._internal.imagebuild.docker_builder import DockerImageBuilder

from stargazer.config import gatk_env, published_image, scrna_env


def publish(image) -> str:
    """Build `image` into the local docker store, push it under its published URI, return that."""
    # `flyte.build()` would push under the content-hash tag only; the
    # builder's `push=False` loads the image into docker to retag it. Private
    # API, so an SDK upgrade can move it.
    asyncio.run(DockerImageBuilder()._build_image(image, push=False))
    target = published_image(image.name)
    subprocess.run(["docker", "tag", image.uri, target], check=True)
    subprocess.run(["docker", "push", target], check=True)
    return target


def main() -> None:
    """Check the version, then publish every task image."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--expect-version")
    args = parser.parse_args()
    version = metadata.version("stargazer")
    if args.expect_version and args.expect_version != version:
        raise SystemExit(
            f"The checkout is version {version}, not {args.expect_version}"
        )
    for env in (gatk_env, scrna_env):
        print(f"published {publish(env.image)}", flush=True)


if __name__ == "__main__":
    main()
