"""
### Unified Flyte initialization.

Selects the right init path based on environment: API key for remote
Union deployments, config file for local development.

spec: [docs/architecture/configuration.md](../architecture/configuration.md)
"""

import os

import flyte


def init(**kwargs):
    """Initialize Flyte from API key (remote) or config (local).

    When FLYTE_API_KEY is set (per-user notebook on Union), initializes
    via API key with project/domain from env vars. Otherwise falls back
    to the local .flyte/config.yaml.
    """
    if os.environ.get("FLYTE_API_KEY"):
        flyte.init_from_api_key(
            project=os.environ.get("FLYTE_PROJECT"),
            domain=os.environ.get("FLYTE_DOMAIN", "development"),
            **kwargs,
        )
    else:
        flyte.init_from_config(**kwargs)
