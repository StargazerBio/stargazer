#!/usr/bin/env python3
"""
Build every domain's task image from this checkout and publish each under the package's version.

The release runs this from the tagged checkout, so each image is built with
the same recipe a checkout runs its tasks on (`task_image()` in
`stargazer.config`): the `env.py` header's environment, then this source. Flyte's local builder builds it with docker and pushes it tagged
by content; the version tag is added to that same manifest, at
`released_image()`, where an installed `stargazer-bio` of that version looks
for it.

Usage:
    pixi run python cli/publish_task_images.py

Needs docker with buildx, signed in to the registry `released_image()` names.
"""

import importlib
import subprocess
from importlib.metadata import version

import flyte

from stargazer.config import PROJECT_ROOT, released_image

TASKS = PROJECT_ROOT / "src" / "stargazer" / "tasks"


def _images() -> list[flyte.Image]:
    """Every domain's task image, from each `tasks/<domain>/env.py`."""
    images = []
    for path in sorted(TASKS.glob("*/env.py")):
        module = importlib.import_module(f"stargazer.tasks.{path.parent.name}.env")
        images += [
            v.image
            for v in vars(module).values()
            if isinstance(v, flyte.TaskEnvironment)
        ]
    return images


def main() -> None:
    """Build, push and version-tag each task image."""
    release = version("stargazer-bio")
    flyte.init(image_builder="local")
    for image in _images():
        target = released_image(image.name, release)
        repository = target.rsplit(":", 1)[0]
        registry, name = repository.rsplit("/", 1)
        built = flyte.build(image.clone(registry=registry, name=name)).uri
        subprocess.run(
            ["docker", "buildx", "imagetools", "create", "--tag", target, built],
            check=True,
        )
        print(f"{image.name}: {target} ({built})")


if __name__ == "__main__":
    main()
