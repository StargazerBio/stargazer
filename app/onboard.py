"""
### Onboarding: give a user their project, access, and dashboard.

Run by an org admin from their own machine, with their own CLI identity; no
privileged credential is deployed anywhere. Each user gets:

1. **A Union user** — found by email, or invited (Union sends the email).
2. **A project**, `u-<handle>`, labeled `managed-by=stargazer` and
   `union-subject=<subject>`. The subject label is the real key: a returning
   user keeps whichever project carries it, whatever it's called. The handle
   (the email's local part unless `--handle` is given) only names new
   projects, and takes a `-2`, `-3`… suffix when the id is taken. Archived
   projects can't be deleted, so their ids stay taken forever.
3. **Access to that project only**: policy `stargazer-<project>` binding the
   built-in `contributor` role on the project's domain, assigned by subject.
   Nothing org-wide.
4. **Their dashboard**, `app.admin_app.app_env` deployed into the project
   with the owner baked in, at the stable subdomain `<project>`. Union
   doesn't reject a second app asking for a taken subdomain (it hangs), so
   uniqueness comes from project ids being unique.

Re-running is safe: every step checks before it writes, so onboarding an
onboarded user only redeploys their dashboard. `upgrade` redeploys every
active Stargazer dashboard; `offboard` stops a user's apps, removes their
access, and archives their project, leaving their notebooks in the store.

The control-plane classes are module attributes so tests can swap in fakes.

Usage (with the deploy settings `app.admin_app.main` needs exported):
    stargazer-users onboard --email jane@uni.edu --first-name Jane --last-name Doe
    stargazer-users upgrade
    stargazer-users offboard --email jane@uni.edu

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import argparse
import asyncio
import re
from functools import cache

import flyte
import flyte.app
from flyte._initialize import get_init_config
from flyte.remote import App, Project
from flyteplugins.union.remote import Assignment, Policy, User

from app import config
from app.admin_app import _build_notebook_image, app_env
from app.init import init
from app.per_notebook import list_project_apps
from stargazer.config import PROJECT_ROOT, logger

_MANAGED = {"managed-by": "stargazer"}
_SUBJECT_LABEL = "union-subject"
# Room for the `u-` prefix and a suffix inside Flyte's id limits.
_HANDLE_MAX = 30


def handle_from_email(email: str) -> str:
    """A project-safe handle from an email's local part (or any name).

    Lowercase `[a-z0-9-]`, no leading or trailing dash, at most 30
    characters. Raises `ValueError` when nothing usable is left.
    """
    local = email.split("@", 1)[0].lower()
    handle = re.sub(r"[^a-z0-9]+", "-", local).strip("-")[:_HANDLE_MAX].strip("-")
    if not handle:
        raise ValueError(f"can't make a handle from {email!r}; pass --handle")
    return handle


def _labels(project) -> dict[str, str]:
    """A project's labels as a plain dict."""
    return dict(project.pb2.labels.values)


def _all_projects() -> tuple[list, list]:
    """Every project in the org: `(active, archived)`."""
    return list(Project.listall()), list(Project.listall(archived=True))


def _owned_by(subject: str, projects: list):
    """The Stargazer project labeled with `subject`, or None."""
    for project in projects:
        labels = _labels(project)
        if (
            labels.get("managed-by") == "stargazer"
            and labels.get(_SUBJECT_LABEL) == subject
        ):
            return project
    return None


def _free_project_id(handle: str, taken: set[str]) -> str:
    """`u-<handle>`, or the first `u-<handle>-N` no project already uses."""
    candidate, n = f"u-{handle}", 2
    while candidate in taken:
        candidate, n = f"u-{handle}-{n}", n + 1
    return candidate


def _find_subject(email: str) -> str | None:
    """The subject of the org member with this email, or None."""
    for user in User.listall(email=email):
        return user.subject
    return None


def _ensure_user(email: str, first_name: str, last_name: str) -> str:
    """The user's subject, inviting them if they aren't an org member yet."""
    subject = _find_subject(email)
    if subject is not None:
        return subject
    logger.info(f"Inviting {email}")
    return User.create(first_name=first_name, last_name=last_name, email=email).subject


def _ensure_project(subject: str, email: str, handle: str) -> str:
    """The user's project id, creating `u-<handle>` (or a suffixed id) if needed."""
    active, archived = _all_projects()
    if (existing := _owned_by(subject, active)) is not None:
        return existing.pb2.id
    taken = {p.pb2.id for p in active + archived}
    project = _free_project_id(handle, taken)
    logger.info(f"Creating project {project} for {email}")
    Project.create(
        id=project,
        name=email,
        description=f"Stargazer notebooks for {email}",
        labels={**_MANAGED, _SUBJECT_LABEL: subject},
    )
    return project


def _policy_name(project: str) -> str:
    """The access policy for one user's project."""
    return f"stargazer-{project}"


def _assigned(subject: str) -> list[str]:
    """Names of the policies assigned to a user; none for a brand-new user."""
    try:
        return list(Assignment.get(user_subject=subject).policies)
    except Exception:
        return []


def _ensure_access(subject: str, project: str) -> None:
    """Bind `contributor` on the project's domain and assign it to the user."""
    name = _policy_name(project)
    try:
        Policy.get(name)
    except Exception:
        Policy.create(
            name,
            description=f"Stargazer: contributor on {project} only",
            bindings=[
                {
                    "role": "contributor",
                    "resource": {"project": project, "domain": config.FLYTE_DOMAIN},
                }
            ],
        )
    if name not in _assigned(subject):
        Assignment.create(user_subject=subject, policy=name)


@cache
def _notebook_image() -> str:
    """The notebook image URI, built (or found in the registry) once per run."""
    return _build_notebook_image()


def deploy_dashboard(project: str, owner_subject: str) -> str:
    """Deploy the dashboard into `project` for its owner; return its URL.

    Same app definition for every user: only the project, the owner and the
    subdomain differ. Images are content-hashed, so a release builds each
    once and every user's dashboard runs the same build.
    """
    env_vars = {
        **app_env.env_vars,
        "FLYTE_PROJECT": project,
        "SG_OWNER_SUBJECT": owner_subject,
        "STARGAZER_NOTEBOOK_IMAGE": _notebook_image(),
    }
    # In-cluster init can't discover the org in an app pod; bake the deployer's.
    if org := get_init_config().org:
        env_vars["FLYTE_ORG"] = org
    env = app_env.clone_with(
        name=app_env.name,
        env_vars=env_vars,
        domain=flyte.app.Domain(subdomain=project),
    )
    ctx = flyte.with_servecontext(project=project, domain=config.FLYTE_DOMAIN)
    # The serve watch can report failure on a redeploy that actually
    # succeeded (devbox_workarounds.md). Trust the app's own state over it.
    try:
        return ctx.serve(env).endpoint
    except RuntimeError as exc:
        app = App.get(name=env.name, project=project, domain=config.FLYTE_DOMAIN)
        if not (app.is_active() and app.endpoint):
            raise
        logger.warning(f"Serve watch for {project} reported {exc}; the app is active")
        return app.endpoint


def stop_project_apps(project: str) -> list[str]:
    """Deactivate every active app in the project; return their names."""

    async def _stop() -> list[str]:
        stopped = []
        for listed in await list_project_apps(project, domain=config.FLYTE_DOMAIN):
            app = await App.get.aio(
                name=listed.name, project=project, domain=config.FLYTE_DOMAIN
            )
            if app.is_active():
                await app.deactivate.aio()
                stopped.append(listed.name)
        return stopped

    return asyncio.run(_stop())


def onboard(
    email: str, first_name: str, last_name: str, handle: str | None = None
) -> str:
    """Give a user their project, access and dashboard; return the dashboard URL."""
    handle = handle_from_email(handle or email)
    subject = _ensure_user(email, first_name, last_name)
    project = _ensure_project(subject, email, handle)
    _ensure_access(subject, project)
    return deploy_dashboard(project, subject)


def upgrade() -> list[str]:
    """Redeploy every active Stargazer dashboard; return their URLs."""
    active, _ = _all_projects()
    urls = []
    for project in active:
        labels = _labels(project)
        if labels.get("managed-by") != "stargazer" or not labels.get(_SUBJECT_LABEL):
            continue
        urls.append(deploy_dashboard(project.pb2.id, labels[_SUBJECT_LABEL]))
    return urls


def offboard(email: str) -> None:
    """Stop a user's apps, remove their access, and archive their project.

    Their workspace notebooks stay in the store. Raises `LookupError` when the
    email has no Stargazer project.
    """
    subject = _find_subject(email)
    active, _ = _all_projects()
    project = _owned_by(subject, active) if subject else None
    if project is None:
        raise LookupError(f"no Stargazer project for {email}")
    pid = project.pb2.id
    stop_project_apps(pid)
    if _policy_name(pid) in _assigned(subject):
        Assignment.unassign(user_subject=subject, policy=_policy_name(pid))
    project.archive()


def main() -> None:
    """CLI entrypoint: `stargazer-users onboard|upgrade|offboard`."""
    parser = argparse.ArgumentParser(
        prog="stargazer-users",
        description="Give Stargazer users their project, access and dashboard.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("onboard", help="give a user their project and dashboard")
    add.add_argument("--email", required=True)
    add.add_argument("--first-name", required=True)
    add.add_argument("--last-name", required=True)
    add.add_argument(
        "--handle", help="names the project; default: the email's local part"
    )
    sub.add_parser("upgrade", help="redeploy every user's dashboard")
    remove = sub.add_parser(
        "offboard", help="stop a user's apps and archive their project"
    )
    remove.add_argument("--email", required=True)
    args = parser.parse_args()

    # Same guard as the dashboard deploy: without a root nothing can be saved.
    if (
        args.command != "offboard"
        and config.TARGET == "union"
        and not config.WORKSPACE_ROOT
    ):
        raise SystemExit(
            "STARGAZER_WORKSPACE_ROOT is not set; export it before deploying."
        )
    init(config.FLYTE_CONFIG, root_dir=PROJECT_ROOT)
    if args.command == "onboard":
        url = onboard(args.email, args.first_name, args.last_name, handle=args.handle)
        print(f"Dashboard: {url}")
    elif args.command == "upgrade":
        for url in upgrade():
            print(f"Dashboard: {url}")
    else:
        offboard(args.email)
        print(f"Offboarded {args.email}")


if __name__ == "__main__":
    main()
