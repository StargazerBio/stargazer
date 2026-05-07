"""
### Marimo notebook Flyte App entrypoint.

Glue between the `note_env` AppEnvironment (declared in stargazer.config)
and the marimo notebook server. Researchers use Marimo notebooks to
explore data, run tasks, and visualize results — bridging exploratory
work and production workflows.

Local development:
    marimo edit src/stargazer/notebooks/byod.py

Run locally as a `docker run` container:
    docker run -p 8080:8080 ghcr.io/stargazerbio/stargazer-note:latest

Deploy hosted to Flyte:
    stargazer-app

spec: [docs/architecture/notebook.md](../docs/architecture/notebook.md)
"""

import os
import signal
import sys
from pathlib import Path

import flyte

from stargazer.config import note_env


def main():
    """Deploy the Marimo notebook app to Flyte."""
    flyte.init_from_config(root_dir=Path(__file__).parent)
    app = flyte.serve(note_env)
    print(f"App URL: {app.url}")

    def _shutdown(signum, frame):
        """Handle SIGINT/SIGTERM by killing the entire process group."""
        pid = app._process.pid
        try:
            # Kill the whole process group (marimo + its children)
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        app.deactivate(wait=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    app._process.wait()


if __name__ == "__main__":
    main()
