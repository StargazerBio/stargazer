"""
### Unified Flyte initialization.

Selects the right init path for the runtime context:
- in-cluster App pod (`_U_EP_OVERRIDE` set) → `flyte.init_in_cluster()`,
  which reads `_U_EP_OVERRIDE`, `_U_INSECURE`, `EAGER_API_KEY`, etc. and
  builds the right client. Mirrors what the `fserve` binary itself does
  before spawning the app subprocess — needed because uvicorn runs in a
  separate process and does not inherit fserve's Python-side client init.
- an API key in `FLYTE_API_KEY` (a deployer running `stargazer-users` with
  one, or a notebook given one) → `flyte.init_from_api_key()`, with what the
  config file would otherwise supply: the remote image builder on Union, and
  `app.config`'s project and domain
- local dev / deployer shell → `flyte.init_from_config()`, reading the
  target's config file (`app.config.FLYTE_CONFIG`) when one is passed

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import os

import flyte

from app import config
from stargazer.config import logger


def init(path_or_config=None, **kwargs):
    """Initialize Flyte for the current runtime context.

    `path_or_config` only applies to the config-file path (the deployer's shell);
    in-cluster and API-key inits ignore it.
    """
    if os.environ.get("FLYTE_API_KEY"):
        logger.info("Flyte init: api-key path (FLYTE_API_KEY)")
        # An API key carries no config file, so nothing else says Union's images
        # come from its remote builder (the local default needs a registry the
        # deployer can push to), or names the project image builds run in.
        kwargs.setdefault(
            "image_builder", "remote" if config.TARGET == "union" else "local"
        )
        flyte.init_from_api_key(
            project=config.FLYTE_PROJECT, domain=config.FLYTE_DOMAIN, **kwargs
        )
    elif os.environ.get("_U_EP_OVERRIDE"):
        logger.info("Flyte init: in-cluster path (_U_EP_OVERRIDE)")
        # `with_servecontext(project=...)` does not propagate to the client
        # used for code-bundle upload during serve, so we must seed a default
        # project on init. `FLYTE_PROJECT` is set in `app_env.env_vars`.
        # App pods don't get `_U_ORG_NAME` (the default org source), so the
        # deployer bakes `FLYTE_ORG`; without it org-scoped calls fail
        # validation with an empty organization.
        flyte.init_in_cluster(
            org=os.environ.get("FLYTE_ORG"),
            project=os.environ.get("FLYTE_PROJECT"),
            domain=os.environ.get("FLYTE_DOMAIN", "development"),
        )
    else:
        logger.info("Flyte init: config-file path")
        flyte.init_from_config(path_or_config, **kwargs)
