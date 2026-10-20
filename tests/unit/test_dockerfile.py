"""Tests for the `Dockerfile` that builds the human-runnable `stargazer` image.

The image runs `app/proxy.py` the way the hosted notebook image does, so it
mirrors `notebook_app_img_recipe` in `app/per_notebook.py`: the proxy's pip
packages, and the static files it reads beside itself in `/usr/local/lib/`.
Nothing ties the two recipes together, and a gap crashes `docker run` at start.
"""

import re
import shlex
from pathlib import Path

from app.per_notebook import notebook_app_img_recipe

ROOT = Path(__file__).resolve().parents[2]


def _instructions() -> list[list[str]]:
    """The Dockerfile's instructions, each joined across `\\` continuations and split."""
    text = re.sub(r"\\\n", " ", (ROOT / "Dockerfile").read_text())
    return [
        shlex.split(line)
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_dockerfile_ships_every_file_the_proxy_reads_beside_itself():
    """The proxy reads these at import."""
    proxy_src = (ROOT / "app" / "proxy.py").read_text()
    needed = set(re.findall(r'Path\(__file__\)\.parent / "([^"]+)"', proxy_src))
    copied = {
        Path(src).name
        for op, *args in _instructions()
        if op == "COPY" and args[-1] == "/usr/local/lib/"
        for src in args[:-1]
    }
    assert "terminal_overlay.html" in needed
    assert needed - copied == set()


def test_dockerfile_installs_every_package_the_hosted_image_pins():
    """Same specs as the hosted image, so the proxy's imports resolve."""
    pinned = {
        pkg
        for layer in notebook_app_img_recipe._layers
        if type(layer).__name__ == "PipPackages"
        for pkg in layer.packages
    }
    installed = {
        word
        for op, *args in _instructions()
        if op == "RUN" and "/opt/venv/bin/pip" in args
        for word in args[args.index("install", args.index("/opt/venv/bin/pip")) :]
    }
    assert any(pkg.startswith("marimo==") for pkg in pinned)
    assert pinned - installed == set()
