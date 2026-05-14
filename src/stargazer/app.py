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


import flyte

from stargazer.config import PROJECT_ROOT, note_env


def main():
    """Deploy the Marimo notebook app to Flyte."""
    flyte.init_from_config(root_dir=PROJECT_ROOT)
    app = flyte.serve(note_env)
    print(f"App URL: {app.url}")


if __name__ == "__main__":
    main()
