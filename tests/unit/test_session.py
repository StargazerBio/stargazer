"""Tests for per-pod session keys and passes (`app.session`)."""

from app.session import (
    SessionData,
    create_pod_pass,
    create_session_cookie,
    pod_key,
    read_pod_pass,
    read_session_cookie,
)


def test_pod_key_is_stable_and_scoped_to_project_and_app():
    """Same inputs give the same key; changing project or app changes it."""
    key = pod_key("master", "octocat", "nb-demo-edit")
    assert key == pod_key("master", "octocat", "nb-demo-edit")
    assert key != pod_key("master", "mallory", "nb-demo-edit")
    assert key != pod_key("master", "octocat", "nb-demo-run")
    assert key != pod_key("other-master", "octocat", "nb-demo-edit")
    assert "master" not in key


def test_pod_pass_roundtrips_only_under_its_key():
    """A pass carries the username and opens only the pod it was minted for."""
    key = pod_key("master", "octocat", "nb-demo-edit")
    pod_pass = create_pod_pass(key, "octocat")
    assert read_pod_pass(pod_pass, key) == "octocat"
    assert read_pod_pass(pod_pass, pod_key("master", "mallory", "nb-demo-edit")) is None


def test_pod_pass_is_not_an_admin_session():
    """A pass leaked from a pod can't be replayed as an admin session cookie."""
    key = pod_key("master", "octocat", "nb-demo-edit")
    assert read_session_cookie(create_pod_pass(key, "octocat"), "master") is None
    cookie = create_session_cookie(SessionData("octocat", 1), "master")
    assert read_pod_pass(cookie, key) is None
