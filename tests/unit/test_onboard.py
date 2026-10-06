"""Tests for `app.onboard`: provisioning a user's project, access and dashboard.

The control plane is a small in-memory fake standing in for
`flyteplugins.union.remote` (users, policies, assignments) and
`flyte.remote.Project`, swapped in at the module attributes `app.onboard`
calls through. Every call is appended to one log so tests can assert order.
Deploying the dashboard is faked at `app.onboard.deploy_dashboard`.
"""

import sys
from types import SimpleNamespace

import pytest

from app import config, onboard

ALICE = "387300641116005877"
BOB = "111111111111111111"


class FakeUnion:
    """In-memory users, projects, policies and assignments, with a call log."""

    def __init__(self):
        self.log: list[tuple] = []
        self.users: dict[str, str] = {}  # email -> subject
        self.projects: dict[str, dict] = {}  # id -> {"labels", "archived", "name"}
        self.policies: dict[str, list[dict]] = {}
        self.assignments: dict[str, list[str]] = {}  # subject -> policy names
        self.next_subject = 900000000000000000

    # -- installation --------------------------------------------------------

    def install(self, monkeypatch):
        """Point `app.onboard` at this fake."""
        fake = self

        class User:
            @staticmethod
            def listall(email=None, limit=100):
                fake.log.append(("user.list", email))
                if email in fake.users:
                    yield SimpleNamespace(subject=fake.users[email], email=email)

            @staticmethod
            def create(first_name, last_name, email):
                subject = str(fake.next_subject)
                fake.next_subject += 1
                fake.users[email] = subject
                fake.log.append(("user.create", email))
                return SimpleNamespace(subject=subject, email=email)

        class Project:
            def __init__(self, pid):
                self.pid = pid

            @property
            def pb2(self):
                p = fake.projects[self.pid]
                return SimpleNamespace(
                    id=self.pid, labels=SimpleNamespace(values=dict(p["labels"]))
                )

            @staticmethod
            def listall(archived=False, filters=None, sort_by=None):
                return [
                    Project(pid)
                    for pid, p in fake.projects.items()
                    if p["archived"] == archived
                ]

            @staticmethod
            def create(id, name, description="", labels=None):
                assert id not in fake.projects, f"project {id} already exists"
                fake.projects[id] = {
                    "labels": dict(labels or {}),
                    "archived": False,
                    "name": name,
                }
                fake.log.append(("project.create", id))
                return Project(id)

            def archive(self):
                fake.projects[self.pid]["archived"] = True
                fake.log.append(("project.archive", self.pid))
                return self

        class Policy:
            @staticmethod
            def get(name):
                if name not in fake.policies:
                    raise RuntimeError(f"policy {name} not found")
                return SimpleNamespace(name=name, bindings=fake.policies[name])

            @staticmethod
            def create(name, description="", bindings=None):
                fake.policies[name] = list(bindings or [])
                fake.log.append(("policy.create", name))
                return SimpleNamespace(name=name, bindings=fake.policies[name])

        class Assignment:
            @staticmethod
            def get(user_subject=None, creds_subject=None, email=None):
                return SimpleNamespace(
                    policies=list(fake.assignments.get(user_subject, []))
                )

            @staticmethod
            def create(user_subject=None, creds_subject=None, email=None, policy=""):
                fake.assignments.setdefault(user_subject, []).append(policy)
                fake.log.append(("assignment.create", user_subject, policy))

            @staticmethod
            def unassign(user_subject=None, creds_subject=None, email=None, policy=""):
                fake.assignments[user_subject].remove(policy)
                fake.log.append(("assignment.unassign", user_subject, policy))

        def deploy_dashboard(project: str, owner_subject: str) -> str:
            fake.log.append(("deploy", project, owner_subject))
            return f"https://{project}.apps.example"

        def stop_project_apps(project: str) -> list[str]:
            fake.log.append(("apps.stop", project))
            return []

        monkeypatch.setattr(onboard, "User", User)
        monkeypatch.setattr(onboard, "Project", Project)
        monkeypatch.setattr(onboard, "Policy", Policy)
        monkeypatch.setattr(onboard, "Assignment", Assignment)
        monkeypatch.setattr(onboard, "deploy_dashboard", deploy_dashboard)
        monkeypatch.setattr(onboard, "stop_project_apps", stop_project_apps)

    # -- helpers -------------------------------------------------------------

    def writes(self) -> list[tuple]:
        """The log without the read-only lookups."""
        return [entry for entry in self.log if entry[0] != "user.list"]

    def add_project(self, pid: str, subject: str | None, archived: bool = False):
        """Seed a project (a Stargazer one when `subject` is given)."""
        labels = (
            {"managed-by": "stargazer", "union-subject": subject} if subject else {}
        )
        self.projects[pid] = {"labels": labels, "archived": archived, "name": pid}


@pytest.fixture
def union(monkeypatch):
    """A fresh fake control plane installed into `app.onboard`."""
    fake = FakeUnion()
    fake.install(monkeypatch)
    return fake


# ---------------------------------------------------------------------------
# Handles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "handle"),
    [
        ("pryce@stargazer.bio", "pryce"),
        ("Jane.Doe+lab@uni.edu", "jane-doe-lab"),
        ("__x__@a.b", "x"),
        ("a" * 60 + "@a.b", "a" * 30),
    ],
)
def test_handle_comes_from_the_email_local_part(email, handle):
    """Lowercase, `[a-z0-9-]` only, no leading/trailing dashes, kept short."""
    assert onboard.handle_from_email(email) == handle


def test_handle_that_cleans_to_nothing_is_refused():
    """An email whose local part has no usable characters needs `--handle`."""
    with pytest.raises(ValueError, match="--handle"):
        onboard.handle_from_email("___@a.b")


# ---------------------------------------------------------------------------
# onboard
# ---------------------------------------------------------------------------


def test_new_user_is_invited_then_given_project_access_and_dashboard(union):
    """User, project, policy, assignment, dashboard: in that order."""
    url = onboard.onboard("jane@uni.edu", "Jane", "Doe")
    subject = union.users["jane@uni.edu"]
    assert union.writes() == [
        ("user.create", "jane@uni.edu"),
        ("project.create", "u-jane"),
        ("policy.create", "stargazer-u-jane"),
        ("assignment.create", subject, "stargazer-u-jane"),
        ("deploy", "u-jane", subject),
    ]
    assert url == "https://u-jane.apps.example"
    assert union.projects["u-jane"]["labels"] == {
        "managed-by": "stargazer",
        "union-subject": subject,
    }
    assert union.policies["stargazer-u-jane"] == [
        {
            "role": "contributor",
            "resource": {"project": "u-jane", "domain": "development"},
        }
    ]


def test_existing_user_is_found_by_email_not_invited_again(union):
    """An org member who was invited already keeps their subject."""
    union.users["pryce@stargazer.bio"] = ALICE
    onboard.onboard("pryce@stargazer.bio", "Pryce", "User")
    assert ("user.create", "pryce@stargazer.bio") not in union.log
    assert ("deploy", "u-pryce", ALICE) in union.log


def test_rerun_only_redeploys_the_dashboard(union):
    """Onboarding an onboarded user changes nothing but the deploy."""
    onboard.onboard("jane@uni.edu", "Jane", "Doe")
    subject = union.users["jane@uni.edu"]
    union.log.clear()
    url = onboard.onboard("jane@uni.edu", "Jane", "Doe")
    assert union.writes() == [("deploy", "u-jane", subject)]
    assert url == "https://u-jane.apps.example"


def test_existing_project_is_found_by_subject_not_by_name(union):
    """A user keeps the project labeled with their subject, whatever it's called."""
    union.users["pryce@stargazer.bio"] = ALICE
    union.add_project(f"u-{ALICE}", ALICE)
    onboard.onboard("pryce@stargazer.bio", "Pryce", "User")
    assert ("project.create", "u-pryce") not in union.log
    assert ("deploy", f"u-{ALICE}", ALICE) in union.log


def test_taken_handle_gets_a_suffix(union):
    """Another user's project, or any other project, is never reused."""
    union.users["pryce@other.org"] = BOB
    union.add_project("u-pryce", "222222222222222222")  # another Stargazer user
    union.add_project("u-pryce-2", None)  # someone else's project
    onboard.onboard("pryce@other.org", "Pryce", "Other")
    assert ("project.create", "u-pryce-3") in union.log
    assert ("deploy", "u-pryce-3", BOB) in union.log


def test_archived_projects_keep_their_names(union):
    """Archived projects can't be deleted, so their ids stay taken."""
    union.users["pryce@stargazer.bio"] = ALICE
    union.add_project("u-pryce", "333333333333333333", archived=True)
    onboard.onboard("pryce@stargazer.bio", "Pryce", "User")
    assert ("project.create", "u-pryce-2") in union.log


def test_explicit_handle_overrides_the_email(union):
    """`--handle` picks the name when the email's local part is a poor one."""
    onboard.onboard("x9@uni.edu", "Jane", "Doe", handle="Jane Doe")
    assert ("project.create", "u-jane-doe") in union.log


def test_assignment_is_skipped_when_already_in_place(union):
    """A user who already has their policy isn't assigned it twice."""
    union.users["jane@uni.edu"] = ALICE
    union.add_project("u-jane", ALICE)
    union.policies["stargazer-u-jane"] = []
    union.assignments[ALICE] = ["stargazer-u-jane"]
    onboard.onboard("jane@uni.edu", "Jane", "Doe")
    assert union.writes() == [("deploy", "u-jane", ALICE)]


# ---------------------------------------------------------------------------
# upgrade / offboard
# ---------------------------------------------------------------------------


def test_upgrade_redeploys_every_active_stargazer_dashboard(union):
    """Upgrade touches Stargazer projects only, and skips archived ones."""
    union.add_project("u-jane", ALICE)
    union.add_project("u-bob", BOB)
    union.add_project("u-old", "333333333333333333", archived=True)
    union.add_project("flytesnacks", None)
    urls = onboard.upgrade()
    assert sorted(union.writes()) == [
        ("deploy", "u-bob", BOB),
        ("deploy", "u-jane", ALICE),
    ]
    assert sorted(urls) == ["https://u-bob.apps.example", "https://u-jane.apps.example"]


def test_offboard_stops_apps_removes_access_and_archives(union):
    """Offboarding leaves the user's notebooks in the store, and nothing running."""
    onboard.onboard("jane@uni.edu", "Jane", "Doe")
    subject = union.users["jane@uni.edu"]
    union.log.clear()
    onboard.offboard("jane@uni.edu")
    assert union.writes() == [
        ("apps.stop", "u-jane"),
        ("assignment.unassign", subject, "stargazer-u-jane"),
        ("project.archive", "u-jane"),
    ]


def test_offboard_of_unknown_user_changes_nothing(union):
    """An email with no Stargazer project is reported, not guessed at."""
    with pytest.raises(LookupError, match="nobody@uni.edu"):
        onboard.offboard("nobody@uni.edu")
    assert union.writes() == []


# ---------------------------------------------------------------------------
# Release plumbing
# ---------------------------------------------------------------------------


def test_notebook_image_is_the_built_uri(monkeypatch):
    """Dashboards bake in the content-hashed URI the build returns, no retag."""
    monkeypatch.setattr(
        onboard.flyte, "build", lambda img: SimpleNamespace(uri="reg/notebook-app:h1")
    )
    assert onboard.build_notebook_image() == "reg/notebook-app:h1"


def test_union_deploy_without_workspace_root_is_refused(monkeypatch):
    """With nowhere to save notebooks, onboarding stops before touching Union."""
    monkeypatch.setattr(config, "TARGET", "union")
    monkeypatch.setattr(config, "WORKSPACE_ROOT", "")
    monkeypatch.setattr(onboard, "init", lambda *a, **k: pytest.fail("init ran"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "stargazer-users",
            "onboard",
            "--email",
            "a@b.c",
            "--first-name",
            "A",
            "--last-name",
            "B",
        ],
    )
    with pytest.raises(SystemExit, match="STARGAZER_WORKSPACE_ROOT"):
        onboard.main()


def test_dashboard_deploy_keeps_the_env_resolvable(monkeypatch):
    """The served env is built where it's defined, with the owner's settings.

    Flyte resolves `include=` paths and the pod's loader from the frame the
    env was created in; a `clone_with` copy reports `dataclasses.py` instead,
    and the deploy fails on `templates/`.
    """
    served = {}

    def fake_servecontext(**ctx):
        def serve(env):
            served.update(
                ctx=ctx, env=env, env_vars=dict(env.env_vars), domain=env.domain
            )
            return SimpleNamespace(endpoint="https://u-jane.apps.example")

        return SimpleNamespace(serve=serve)

    monkeypatch.setattr(onboard.flyte, "with_servecontext", fake_servecontext)
    monkeypatch.setattr(onboard, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(
        onboard, "get_init_config", lambda: SimpleNamespace(org="stargazerbio")
    )
    assert onboard.deploy_dashboard("u-jane", ALICE) == "https://u-jane.apps.example"
    env = served["env"]
    assert env._caller_frame.filename.endswith("app/admin_app.py")
    assert served["ctx"] == {"project": "u-jane", "domain": "development"}
    assert served["domain"].subdomain == "u-jane"
    assert {
        k: served["env_vars"][k]
        for k in (
            "FLYTE_PROJECT",
            "SG_OWNER_SUBJECT",
            "STARGAZER_NOTEBOOK_IMAGE",
            "FLYTE_ORG",
        )
    } == {
        "FLYTE_PROJECT": "u-jane",
        "SG_OWNER_SUBJECT": ALICE,
        "STARGAZER_NOTEBOOK_IMAGE": "reg/notebook-app:h1",
        "FLYTE_ORG": "stargazerbio",
    }


def test_dashboard_deploy_waits_out_a_stale_watch_failure(monkeypatch):
    """A watch error on a deploy that does come up is not reported as failure.

    Seen on the tenant: the watch tripped on an older failed revision while
    the new one became ready a few seconds later.
    """

    def failing_servecontext(**ctx):
        def serve(env):
            raise RuntimeError("App deployment for app dashboard has failed!")

        return SimpleNamespace(serve=serve)

    states = iter([False, False, True])

    class FakeApp:
        @staticmethod
        def get(name, project, domain):
            active = next(states)
            return SimpleNamespace(
                is_active=lambda: active, endpoint="https://u-jane.apps.example"
            )

    monkeypatch.setattr(onboard.flyte, "with_servecontext", failing_servecontext)
    monkeypatch.setattr(onboard, "App", FakeApp)
    monkeypatch.setattr(onboard, "_notebook_image", lambda: "reg/notebook-app:h1")
    monkeypatch.setattr(onboard.time, "sleep", lambda s: None)
    assert onboard.deploy_dashboard("u-jane", ALICE) == "https://u-jane.apps.example"
