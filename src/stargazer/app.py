"""
### Marimo notebook Flyte App.

Defines the AppEnvironment for deploying Stargazer's interactive notebook
interface. Researchers use Marimo notebooks to explore data, run tasks,
and visualize results — bridging exploratory work and production workflows.

Local development:
    marimo edit src/stargazer/notebooks/getting_started.py

Deploy to Flyte:
    stargazer-app

spec: [docs/architecture/notebook.md](../docs/architecture/notebook.md)
"""

import flyte
import flyte.app

from stargazer.config import STARGAZER_ENV_VARS, STARGAZER_SECRETS

marimo_env = flyte.app.AppEnvironment(
    name="stargazer-notebooks",
    image=flyte.Image.from_debian_base(python_version=(3, 13)).with_pip_packages(
        "marimo>=0.10.0",
        "stargazer",
    ),
    command="marimo run src/stargazer/notebooks/getting_started.py --port 8080 --host 0.0.0.0 --include-code",
    port=8080,
    include=["src/stargazer/notebooks/"],
    resources=flyte.Resources(cpu=2, memory="4Gi"),
    requires_auth=False,
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)


def main():
    """Deploy the Marimo notebook app to Flyte."""
    flyte.init_from_config()
    result = flyte.serve(marimo_env)
    print(result[0])


if __name__ == "__main__":
    main()
