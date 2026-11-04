"""Tests for the task environments' locks against the development lock.

A run is submitted from the development environment (`pixi.lock`) and runs in
a domain's task image (its `env.py.pixi.lock`), and Flyte's wire format
only holds between matching SDKs. The locks are solved apart, so relocking one
can move its `flyte` away from the others.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "stargazer"
ENV_LOCKS = sorted(PACKAGE.rglob("env.py.pixi.lock"))


def _flyte_versions(lock: Path) -> set[str]:
    """Every `flyte` version a pixi lock holds."""
    packages = yaml.safe_load(lock.read_text())["packages"]
    return {pkg["version"] for pkg in packages if pkg.get("name") == "flyte"}


def test_every_environment_is_locked():
    """Each `env.py` has its lock beside it, or its image refuses to build."""
    envs = sorted(PACKAGE.rglob("env.py"))
    assert [e.parent for e in envs] == [lock.parent for lock in ENV_LOCKS]


@pytest.mark.parametrize(
    "lock", ENV_LOCKS, ids=lambda p: str(p.parent.relative_to(PACKAGE))
)
def test_task_image_runs_the_flyte_development_submits_with(lock):
    """The environment's lock pins the same `flyte` as pixi.lock."""
    assert _flyte_versions(lock) == _flyte_versions(ROOT / "pixi.lock")
