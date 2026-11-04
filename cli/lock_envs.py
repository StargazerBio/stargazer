#!/usr/bin/env python3
"""
Lock the task environments: each `src/stargazer/tasks/<domain>/env.py`'s header into the `env.py.pixi.lock` beside it.

A task image installs its environment with `pixi install --locked`, from the
pixi manifest Flyte renders out of the header and the pixi version Flyte's
image builder pins. This locks that same manifest with that same pixi, in
docker, so the build accepts the lock: a lock from `pixi lock --script` by a
newer pixi records the platform's virtual packages in a form the builder's
pixi reads as out of date, and the build refuses it. The existing lock is
kept where the header still allows it, as `pixi lock` keeps it; `--update`
solves from scratch, as `pixi update` does.

Usage:
    pixi run python cli/lock_envs.py [--check] [--update] [env.py ...]

With no paths, it locks every environment. `--check` changes nothing and
exits 1 if any lock is out of date with its header.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from flyte._internal.imagebuild.utils import PIXI_VERSION
from flyte._utils.pixi_script_parser import (
    parse_pixi_script_file,
    platforms_for,
    render_pixi_manifest,
)

from stargazer.config import IMAGE_PLATFORM, PROJECT_ROOT


def lock_path(env: Path) -> Path:
    """Where `pixi lock --script` and Flyte's builder look for `env`'s lock."""
    return env.with_name(f"{env.name}.pixi.lock")


def lock(env: Path, *, check: bool, update: bool) -> bool:
    """Lock `env` (or only check it); return whether its lock was up to date."""
    manifest = render_pixi_manifest(
        parse_pixi_script_file(env), platforms_for(IMAGE_PLATFORM)
    )
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "pixi.toml").write_text(manifest)
        if lock_path(env).exists() and not update:
            shutil.copy(lock_path(env), work / "pixi.lock")
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{work}:/w",
                "-w",
                "/w",
                f"ghcr.io/prefix-dev/pixi:{PIXI_VERSION}",
                "pixi",
                "lock",
                *(["--check"] if check else []),
            ],
            capture_output=True,
            text=True,
            check=False,  # --check's exit code is the result
        )
        if check:
            return result.returncode == 0
        if result.returncode != 0:
            raise SystemExit(f"pixi lock failed for {env}:\n{result.stderr}")
        shutil.copy(work / "pixi.lock", lock_path(env))
        return True


def main(argv: list[str]) -> int:
    """Lock or check the selected environments."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("envs", nargs="*", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    envs = [e.resolve() for e in args.envs] or sorted(
        (PROJECT_ROOT / "src" / "stargazer" / "tasks").glob("*/env.py")
    )
    stale = []
    for env in envs:
        name = env.relative_to(PROJECT_ROOT)
        print(f"{'checking' if args.check else 'locking'} {name}", flush=True)
        if not lock(env, check=args.check, update=args.update):
            stale.append(name)
    for name in stale:
        print(
            f"out of date: {lock_path(PROJECT_ROOT / name).relative_to(PROJECT_ROOT)}"
        )
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
