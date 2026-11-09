# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "stargazer-bio",
#     "scanpy>=1.12",
#     "anndata>=0.12.10",
#     "scikit-image>=0.26.0",
#     "igraph>=1.0.0",
#     "pooch>=1.9.0",
# ]
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
# platforms = ["linux-64", "osx-arm64"]
#
# [tool.pixi.dependencies]
# python = "3.14.*"
# ///
"""
### The scRNA-seq tasks' environment.

`scrna_env`, which every task in `tasks/scrna/` runs on. The header above is
its image's packages: scanpy, plus what its steps import lazily (scikit-image
for scrublet's automatic threshold, igraph for Leiden, pooch for scanpy's
datasets), and the released SDK, whose core dependencies the lock pins.
`cli/lock_envs.py` locks it into `env.py.pixi.lock` beside this file.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import flyte

from stargazer.config import STARGAZER_ENV_VARS, STARGAZER_SECRETS, task_image

# Memory-hungry at runtime because scanpy loads full AnnData objects into RAM.
scrna_env = flyte.TaskEnvironment(
    name="scrna",
    description="scanpy-based single-cell RNA analysis; memory-intensive AnnData workloads",
    image=task_image(__file__),
    resources=flyte.Resources(memory=("2Gi", "6Gi")),
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)
