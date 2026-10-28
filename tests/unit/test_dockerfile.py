"""Tests for `runtime/Dockerfile`, the one Stargazer image.

The proxy reads its HTML fragments from beside itself at import, so a fragment
the image doesn't copy there crashes every pod at start.
"""

import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime"


def _instructions() -> list[list[str]]:
    """The Dockerfile's instructions, each joined across `\\` continuations and split."""
    text = re.sub(r"\\\n", " ", (RUNTIME / "Dockerfile").read_text())
    return [
        shlex.split(line)
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_dockerfile_ships_every_file_the_proxy_reads_beside_itself():
    """The proxy reads these at import."""
    proxy_src = (RUNTIME / "proxy.py").read_text()
    needed = set(re.findall(r'Path\(__file__\)\.parent / "([^"]+)"', proxy_src))
    copied = {
        Path(src).name
        for op, *args in _instructions()
        if op == "COPY" and args[-1] == "/usr/local/lib/"
        for src in args[:-1]
    }
    assert "terminal_overlay.html" in needed
    assert needed - copied == set()
