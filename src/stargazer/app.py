"""
### Marimo notebook Flyte App.

Defines the AppEnvironment for deploying Stargazer's interactive notebook
interface. Researchers use Marimo notebooks to explore data, run tasks,
and visualize results — bridging exploratory work and production workflows.

Local development:
    marimo edit src/stargazer/notebooks/getting_started.py

Run locally via Flyte:
    python src/stargazer/app.py

Deploy to Flyte:
    stargazer-app

spec: [docs/architecture/notebook.md](../docs/architecture/notebook.md)
"""

import sys
from pathlib import Path

import flyte
import flyte.app

from stargazer.config import STARGAZER_ENV_VARS, STARGAZER_SECRETS

marimo_env = flyte.app.AppEnvironment(
    name="stargazer-notebooks",
    image=flyte.Image.from_debian_base(python_version=(3, 13)).with_pip_packages(
        "marimo>=0.10.0",
        "stargazer",
    ),
    args=[sys.executable, "src/stargazer/app.py", "--server"],
    port=8080,
    include=["src/stargazer/notebooks/"],
    resources=flyte.Resources(cpu=2, memory="4Gi"),
    requires_auth=False,
    env_vars=STARGAZER_ENV_VARS,
    secrets=STARGAZER_SECRETS,
)


def _run_server():
    """Start the Marimo notebook server, replacing this process."""
    import os
    import shutil

    marimo_bin = shutil.which("marimo")
    if not marimo_bin:
        raise FileNotFoundError("marimo not found on PATH")

    os.execv(
        marimo_bin,
        [
            "marimo",
            "edit",
            "src/stargazer/notebooks/getting_started.py",
            "--port",
            "8080",
            "--host",
            "0.0.0.0",
            "--headless",
            "--no-token",
        ],
    )


def main():
    """Deploy the Marimo notebook app to Flyte."""
    import signal

    flyte.init_from_config(root_dir=Path(__file__).parent)
    app = flyte.serve(marimo_env)
    print(f"App URL: {app.url}")

    def _shutdown(signum, frame):
        """Handle SIGINT/SIGTERM by deactivating the app."""
        app.deactivate(wait=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    app._process.wait()


if __name__ == "__main__":
    if "--server" in sys.argv:
        _run_server()
    else:
        main()
