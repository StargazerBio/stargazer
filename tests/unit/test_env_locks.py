"""Tests for the task environments' locks against the development lock.

A run is submitted from the development environment (`pixi.lock`) and runs in
a task image (each domain's `env.py.pixi.lock`), and Flyte's wire format only
holds between matching SDKs. The locks are solved apart, so relocking one
can move its `flyte` away from the others.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ENV_LOCKS = sorted((ROOT / "src" / "stargazer" / "tasks").glob("*/env.py.pixi.lock"))


def _flyte_versions(lock: Path) -> set[str]:
    """Every `flyte` version a pixi lock holds."""
    packages = yaml.safe_load(lock.read_text())["packages"]
    return {pkg["version"] for pkg in packages if pkg.get("name") == "flyte"}


def test_every_domain_has_a_locked_environment():
    """Each `env.py` has its lock beside it, or its image refuses to build."""
    envs = sorted((ROOT / "src" / "stargazer" / "tasks").glob("*/env.py"))
    assert [e.parent.name for e in envs] == [lock.parent.name for lock in ENV_LOCKS]


@pytest.mark.parametrize("lock", ENV_LOCKS, ids=lambda p: p.parent.name)
def test_task_image_runs_the_flyte_development_submits_with(lock):
    """The environment's lock pins the same `flyte` as pixi.lock."""
    assert _flyte_versions(lock) == _flyte_versions(ROOT / "pixi.lock")
