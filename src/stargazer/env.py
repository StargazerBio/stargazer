# /// script
# requires-python = ">=3.14"
# dependencies = ["stargazer-bio"]
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
# platforms = ["linux-64"]
#
# [tool.pixi.dependencies]
# python = "3.14.*"
# ///
"""
### The core environment.

The released SDK and its core dependencies alone, for tasks that need nothing
more, such as the ones a notebook defines: `task_image(CORE_ENV, name)` builds
it like a domain's environment, with the checkout's source on top. It holds
no `TaskEnvironment` of its own. `cli/lock_envs.py` locks the header above
into `env.py.pixi.lock` beside this file.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

from pathlib import Path

CORE_ENV = Path(__file__)
