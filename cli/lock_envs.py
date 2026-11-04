#!/usr/bin/env python3
"""
Lock the environments images install: pyproject.toml's into pixi.lock, and each domain's `env.py` header into the `env.py.pixi.lock` beside it.

An image installs its environment with `pixi install --locked`, run by the
pixi version Flyte's image builder pins, which refuses a lock a newer pixi
wrote: the two record the platform's virtual packages differently. So this
locks with that same pixi, fetched from conda-forge by `pixi exec`.
pyproject.toml is locked in place, since its SDK is an editable path into the
checkout. A header is locked as the pixi manifest Flyte renders from it, in a
directory of its own. The existing lock is kept where the manifest still
allows it, as `pixi lock` keeps it; `--update` solves from scratch, as
`pixi update` does.

Usage:
    pixi run python cli/lock_envs.py [--check] [--update] [pyproject.toml | env.py ...]

With no paths, it locks pyproject.toml and every domain's
`src/stargazer/tasks/<domain>/env.py`. `--check` changes nothing and exits 1
if relocking would change any lock.
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

PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def lock_path(manifest: Path) -> Path:
    """Where pixi and Flyte's builder look for `manifest`'s lock."""
    if manifest == PYPROJECT:
        return PROJECT_ROOT / "pixi.lock"
    return manifest.with_name(f"{manifest.name}.pixi.lock")


def manifests() -> list[Path]:
    """pyproject.toml and every domain's `env.py`."""
    return [PYPROJECT, *sorted((PROJECT_ROOT / "src" / "stargazer").rglob("env.py"))]


def pixi_lock(manifest: Path) -> None:
    """Lock `manifest` with the builder's pixi, beside it."""
    result = subprocess.run(
        [
            "pixi",
            "exec",
            "--spec",
            f"pixi=={PIXI_VERSION}",
            "--",
            "pixi",
            "lock",
            # Under `pixi run`, the variables pixi sets name this checkout's
            # manifest, which the flag overrides.
            "--manifest-path",
            str(manifest),
        ],
        capture_output=True,
        text=True,
        check=False,  # a failed solve is reported below
    )
    if result.returncode != 0:
        raise SystemExit(f"pixi lock failed for {manifest}:\n{result.stderr}")


def lock(manifest: Path, *, check: bool, update: bool) -> bool:
    """Lock `manifest` (with `check`, put the lock back after); return whether its lock changed."""
    lock_file = lock_path(manifest)
    current = lock_file.read_bytes() if lock_file.exists() else b""
    if manifest == PYPROJECT:
        if update:
            lock_file.unlink(missing_ok=True)
        try:
            pixi_lock(manifest)
            locked = lock_file.read_bytes()
        finally:
            if check:
                lock_file.write_bytes(current)
        return locked != current
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "pixi.toml").write_text(
            render_pixi_manifest(
                parse_pixi_script_file(manifest), platforms_for(IMAGE_PLATFORM)
            )
        )
        if current and not update:
            shutil.copy(lock_file, work / "pixi.lock")
        pixi_lock(work / "pixi.toml")
        # This pixi's own `lock --check` exits 0 on a lock it has just
        # rewritten, so a check compares the relocked file instead.
        locked = (work / "pixi.lock").read_bytes()
    if not check:
        lock_file.write_bytes(locked)
    return locked != current


def main(argv: list[str]) -> int:
    """Lock or check the selected manifests."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("manifests", nargs="*", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    if args.check and args.update:
        parser.error("--check compares against the lock --update would replace")
    selected = [m.resolve() for m in args.manifests] or manifests()
    stale = []
    for manifest in selected:
        if manifest != PYPROJECT and (
            manifest.name != "env.py" or not manifest.is_file()
        ):
            parser.error(f"{manifest} is neither pyproject.toml nor an env.py")
        changed = lock(manifest, check=args.check, update=args.update)
        verb = "out of date" if args.check else "locked"
        print(f"{verb if changed else 'up to date'}: {lock_path(manifest)}", flush=True)
        if args.check and changed:
            stale.append(manifest)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
