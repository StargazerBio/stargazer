"""Tests for log_execution in config, run in real git repositories."""

import os
import re
import subprocess
from pathlib import Path

import pytest

import stargazer.config as config_mod
from stargazer.config import log_execution


@pytest.fixture(autouse=True)
def no_git_env(monkeypatch):
    """Drop every GIT_* variable, so git finds the tmp repos and not the caller's.

    Git exports GIT_INDEX_FILE (and from some callers GIT_DIR) to hooks such as
    pre-commit. Inherited, they point `git add` at the real index and make
    `git init` reinitialize the real repository, flipping its core.bare.
    """
    for name in [n for n in os.environ if n.startswith("GIT_")]:
        monkeypatch.delenv(name)


def _git(cwd, *args) -> str:
    """Run git in `cwd` and return its stdout."""
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def logs(tmp_path, monkeypatch):
    """Execution logs go to a temp dir; returns it."""
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(config_mod, "_log_dir", logs)
    return logs


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A git repository with one commit, as the working directory; returns its short hash."""
    work = tmp_path / "repo"
    work.mkdir()
    _git(work, "init", "-q")
    (work / "a.txt").write_text("a\n")
    _git(work, "add", "a.txt")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    monkeypatch.chdir(work)
    return _git(work, "rev-parse", "--short", "HEAD")


def test_clean_repo_names_the_caller_commit_and_time(repo, logs):
    """The ID is <caller>-<commit>-<UTC timestamp>, and its log file is created."""
    execution_id = log_execution()

    assert re.fullmatch(
        rf"test_clean_repo_names_the_caller_commit_and_time-{repo}-\d{{8}}T\d{{6}}Z",
        execution_id,
    )
    assert [p.name for p in logs.iterdir()] == [f"{execution_id}.log"]


def test_dirty_repo_tags_the_commit(repo, logs):
    """Uncommitted changes mark the commit `-dirty`."""
    Path("b.txt").write_text("b\n")

    assert f"-{repo}-dirty-" in log_execution()


def test_outside_a_repo_the_commit_is_unknown(tmp_path, logs, monkeypatch):
    """No repository, no commit to name."""
    outside = tmp_path / "plain"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    execution_id = log_execution()

    assert "-unknown-" in execution_id
    assert "-dirty" not in execution_id
