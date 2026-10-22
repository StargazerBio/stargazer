"""Deploy, inspect and stop the Union test account's dashboard (`u-pryce`).

Touches only that one dashboard; `stargazer-users upgrade` would redeploy
every user's. Run from the checkout root with `STARGAZER_TARGET=union`
exported (and the deploy settings, for `deploy`).

    union_dashboard.py deploy        # redeploy it from this checkout
    union_dashboard.py check <app>   # an app's served image, its pod's base, recent runs
    union_dashboard.py teardown      # stop every active app in the project
"""

import argparse

from flyte.remote import App, Run

from app import config
from app.deploy import (
    active_runs,
    deploy_dashboard,
    refuse_while_running,
    release_version,
    stop_project_apps,
)
from app.init import init
from stargazer.config import PROJECT_ROOT

PROJECT, SUBJECT = "u-pryce", "387300641116005877"


def check(name: str) -> None:
    """Print the app's served image, its pod's notebook base, and the newest runs."""
    app = App.get(name=name, project=PROJECT, domain=config.FLYTE_DOMAIN)
    container = app.pb2.spec.container
    env = {e.key: e.value for e in container.env}
    print("active:", app.is_active())
    print("served image:", container.image)
    print("pod STARGAZER_NOTEBOOK_IMAGE:", env.get("STARGAZER_NOTEBOOK_IMAGE"))
    for run in Run.listall(
        project=PROJECT,
        domain=config.FLYTE_DOMAIN,
        limit=3,
        sort_by=("created_at", "desc"),
    ):
        print("run:", run.name, run.phase, run.pb2.action.metadata.task.id.name)


def main() -> None:
    """Dispatch the subcommand."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("deploy")
    sub.add_parser("check").add_argument("app")
    sub.add_parser("teardown")
    args = parser.parse_args()

    init(config.FLYTE_CONFIG, root_dir=PROJECT_ROOT)
    if args.command == "deploy":
        refuse_while_running([PROJECT])
        print("version:", release_version())
        print("Dashboard:", deploy_dashboard(PROJECT, SUBJECT))
    elif args.command == "check":
        check(args.app)
    else:
        print("stopped:", stop_project_apps(PROJECT))
        print("live runs:", active_runs(PROJECT))


if __name__ == "__main__":
    main()
