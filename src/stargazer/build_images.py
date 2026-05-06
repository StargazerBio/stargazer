"""
### Build and push every Stargazer environment image.

Iterates the four module-level environments in stargazer.config —
`scrna_env`, `gatk_env`, `note_env`, `chat_env` — and calls
`flyte.build_images()` on each. With `image.builder = local` set in
`.flyte/config.yaml`, this builds locally via Docker and pushes to the
configured registry; run `docker login` first.

Equivalent to running `flyte build src/stargazer/config.py <env>` once
per env, but without the per-invocation init overhead.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

from pathlib import Path

import flyte

from stargazer.config import (
    PROJECT_ROOT,
    chat_env,
    gatk_env,
    logger,
    note_env,
    scrna_env,
)


def main():
    """Build and push images for every Stargazer environment."""
    flyte.init_from_config(root_dir=Path(PROJECT_ROOT))

    for env in (scrna_env, gatk_env, note_env, chat_env):
        logger.info(f"Building image for env: {env.name}")
        cache = flyte.build_images(env)
        logger.info(f"{env.name}: {cache!r}")


if __name__ == "__main__":
    main()
