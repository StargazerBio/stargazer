"""
### Build Stargazer's Flyte task images locally.

Iterates the per-task Flyte environments declared in `stargazer.config` —
`scrna_env` and `gatk_env` — and calls `flyte.build_images()` on each.
With `image.builder = local` in `.flyte/config.yaml` and no `registry=`
set on the images, the docker builder runs with `--load` and the result
stays in the local docker cache (no push, no registry credentials needed).
CI is expected to publish to the hosted registry on merge to main.

Equivalent to running `flyte build src/stargazer/config.py <env>` once
per env, but without the per-invocation init overhead.

The human-runnable images (note, chat) are built from the project's
`Dockerfile` instead — see `docs/guides/contributing.md` for the
`docker build --target {note,chat}` commands.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

from pathlib import Path

import flyte

from stargazer.config import (
    PROJECT_ROOT,
    gatk_env,
    logger,
    scrna_env,
)


def main():
    """Build and push images for every Flyte task environment."""
    flyte.init_from_config(root_dir=Path(PROJECT_ROOT))

    for env in (scrna_env, gatk_env):
        logger.info(f"Building image for env: {env.name}")
        cache = flyte.build_images(env)
        logger.info(f"{env.name}: {cache!r}")


if __name__ == "__main__":
    main()
