"""
### Marimo notebook Flyte App entrypoint.

Glue between the `note_env` AppEnvironment (declared in stargazer.config)
and the marimo notebook server. Researchers use Marimo notebooks to
explore data, run tasks, and visualize results — bridging exploratory
work and production workflows.

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

from stargazer.config import note_env


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
    import os
    import signal

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
    if "--server" in sys.argv:
        _run_server()
    else:
        main()
