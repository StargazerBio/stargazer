# /// script
# requires-python = ">=3.14"
# dependencies = ["stargazer-bio"]
#
# [tool.pixi.workspace]
# # bioconda's packages build against conda-forge's, which come first.
# channels = ["conda-forge", "bioconda"]
# platforms = ["linux-64"]
#
# [tool.pixi.dependencies]
# python = "3.14.*"
# gatk4 = "4.6.*"
# samtools = "1.*"
# bwa = "0.7.*"
# bwa-mem2 = "2.*"
# ///
"""
### The GATK and alignment tasks' environment.

`gatk_env`, which every task in `tasks/gatk/` and `tasks/general/` runs on,
and the workflows that chain them. The header above is its image's packages:
gatk4 (with the JVM its wrapper calls), samtools, bwa and bwa-mem2 from
bioconda, on the pod's PATH from the environment, and the released SDK, whose
core dependencies the lock pins. `cli/lock_envs.py` locks it into
`env.py.pixi.lock` beside this file.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import flyte

from stargazer.config import STARGAZER_ENV_VARS, STARGAZER_SECRETS, task_image

gatk_env = flyte.TaskEnvironment(
    name="gatk",
    description="GATK, BWA, and samtools alignment and variant-calling workloads",
    image=task_image(__file__),
    # A 1Gi request: the germline workflow holds three gatk_env pods at once
    # (workflow, prepare_reference or preprocess_sample, the tool), and three
    # 2Gi requests don't fit the devbox node beside a dashboard.
    resources=flyte.Resources(memory=("1Gi", "6Gi")),
    # For the devbox, whose projects' settings don't reach task pods; a
    # hosted project's settings carry these.
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)
