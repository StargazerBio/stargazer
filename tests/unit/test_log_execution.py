"""Tests for log_execution in config."""

import re
from unittest.mock import patch

from stargazer.config import log_execution


def test_log_execution_clean_repo(tmp_path):
    """Returns execution ID with caller name, commit hash, and timestamp."""
    with (
        patch("stargazer.config._log_dir", tmp_path),
        patch("stargazer.config.subprocess.run") as mock_run,
    ):
        mock_run.side_effect = [
            type("Result", (), {"stdout": "abc1234\n", "returncode": 0})(),
            type("Result", (), {"stdout": "", "returncode": 0})(),
        ]
        execution_id = log_execution()

    # Format: <caller>-<hash>-<timestamp>
    assert execution_id.startswith("test_log_execution_clean_repo-")
    assert "abc1234" in execution_id
    assert re.search(r"-\d{8}T\d{6}Z$", execution_id)
    assert "-dirty" not in execution_id

    # Log file was created
    log_files = list(tmp_path.glob("*.log"))
    assert len(log_files) == 1
    assert execution_id in log_files[0].name


def test_log_execution_dirty_repo(tmp_path, capfd):
    """Tags commit with -dirty and warns when git tree is unclean."""
    with (
        patch("stargazer.config._log_dir", tmp_path),
        patch("stargazer.config.subprocess.run") as mock_run,
    ):
        # First call: git rev-parse, second call: git status
        mock_run.side_effect = [
            type("Result", (), {"stdout": "abc1234\n", "returncode": 0})(),
            type("Result", (), {"stdout": "M config.py\n", "returncode": 0})(),
        ]
        execution_id = log_execution()

    assert "abc1234-dirty" in execution_id


def test_log_execution_git_unavailable(tmp_path):
    """Falls back to 'unknown' when git is not available."""
    with (
        patch("stargazer.config._log_dir", tmp_path),
        patch("stargazer.config.subprocess.run") as mock_run,
    ):
        mock_run.side_effect = [
            type("Result", (), {"stdout": "", "returncode": 128})(),
            type("Result", (), {"stdout": "", "returncode": 128})(),
        ]
        execution_id = log_execution()

    assert "unknown" in execution_id
    assert "-dirty" not in execution_id
