"""
### Unified Flyte initialization.

Selects the right init path for the runtime context:
- in-cluster App pod (`_U_EP_OVERRIDE` set) → `flyte.init_in_cluster()`,
  which reads `_U_EP_OVERRIDE`, `_U_INSECURE`, `EAGER_API_KEY`, etc. and
  builds the right client. Mirrors what the `fserve` binary itself does
  before spawning the app subprocess — needed because uvicorn runs in a
  separate process and does not inherit fserve's Python-side client init.
- per-user notebook with `FLYTE_API_KEY` → `flyte.init_from_api_key()`
- local dev / deployer shell → `flyte.init_from_config()` (reads
  `.flyte/config.yaml`)

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os

import flyte

from stargazer.config import logger


def init(**kwargs):
    """Initialize Flyte for the current runtime context."""
    if os.environ.get("FLYTE_API_KEY"):
        logger.info("Flyte init: api-key path (FLYTE_API_KEY)")
        flyte.init_from_api_key(
            project=os.environ.get("FLYTE_PROJECT"),
            domain=os.environ.get("FLYTE_DOMAIN", "development"),
            **kwargs,
        )
    elif os.environ.get("_U_EP_OVERRIDE"):
        logger.info("Flyte init: in-cluster path (_U_EP_OVERRIDE)")
        # `with_servecontext(project=...)` does not propagate to the client
        # used for code-bundle upload during serve, so we must seed a default
        # project on init. `FLYTE_PROJECT` is set in `app_env.env_vars`.
        flyte.init_in_cluster(
            project=os.environ.get("FLYTE_PROJECT"),
            domain=os.environ.get("FLYTE_DOMAIN", "development"),
        )
    else:
        logger.info("Flyte init: config-file path")
        flyte.init_from_config(**kwargs)
