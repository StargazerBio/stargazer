#!/usr/bin/env python3
"""
Lock the task environments: each `env.py`'s header under `src/stargazer/` into the `env.py.pixi.lock` beside it.

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

With no paths, it locks every environment: each domain's
(`src/stargazer/tasks/<domain>/env.py`) and the core one
(`src/stargazer/env.py`). `--check` changes nothing and exits 1 if relocking
would change any lock. Needs docker.
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


def environments() -> list[Path]:
    """Every environment's `env.py` in the package."""
    return sorted((PROJECT_ROOT / "src" / "stargazer").rglob("env.py"))


def lock(env: Path, *, check: bool, update: bool) -> bool:
    """Lock `env` (or with `check`, only relock a copy); return whether its lock changed."""
    manifest = render_pixi_manifest(
        parse_pixi_script_file(env), platforms_for(IMAGE_PLATFORM)
    )
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "pixi.toml").write_text(manifest)
        if lock_path(env).exists() and not update:
            shutil.copy(lock_path(env), work / "pixi.lock")
        if shutil.which("docker") is None:
            raise SystemExit("lock_envs.py runs pixi in docker: install docker")
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
            ],
            capture_output=True,
            text=True,
            check=False,  # a failed solve is reported below
        )
        if result.returncode != 0:
            raise SystemExit(f"pixi lock failed for {env}:\n{result.stderr}")
        # This pixi's own `lock --check` exits 0 on a lock it has just
        # rewritten, so a check compares the relocked file instead.
        locked = (work / "pixi.lock").read_bytes()
        current = lock_path(env).read_bytes() if lock_path(env).exists() else b""
        if not check:
            lock_path(env).write_bytes(locked)
        return locked != current


def main(argv: list[str]) -> int:
    """Lock or check the selected environments."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("envs", nargs="*", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    if args.check and args.update:
        parser.error("--check compares against the lock --update would replace")
    envs = [e.resolve() for e in args.envs] or environments()
    stale = []
    for env in envs:
        if env.name != "env.py" or not env.is_file():
            parser.error(f"{env} is not an environment's env.py")
        changed = lock(env, check=args.check, update=args.update)
        verb = "out of date" if args.check else "locked"
        print(f"{verb if changed else 'up to date'}: {lock_path(env)}", flush=True)
        if args.check and changed:
            stale.append(env)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
