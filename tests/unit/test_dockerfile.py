"""Tests for the `Dockerfile` that builds the human-runnable `stargazer` image.

The image bakes `app/proxy.py` and the static files it reads beside itself into
`/usr/local/lib/`, mirroring `notebook_app_img_recipe` in `app/per_notebook.py`.
Nothing ties the two recipes together, so a file the proxy starts reading has to
be added to both.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _copied_into(dest: str) -> set[str]:
    """Names of the `app/` files the Dockerfile's `COPY` lines put in `dest`."""
    names = set()
    for line in (ROOT / "Dockerfile").read_text().splitlines():
        args = [a for a in line.split()[1:] if not a.startswith("--")]
        if line.startswith("COPY ") and args[-1] == dest:
            names |= {Path(src).name for src in args[:-1] if src.startswith("app/")}
    return names


def test_dockerfile_ships_every_file_the_proxy_reads_beside_itself():
    """The proxy reads these at import, so a missing one crashes `docker run`."""
    proxy_src = (ROOT / "app" / "proxy.py").read_text()
    needed = set(re.findall(r'Path\(__file__\)\.parent / "([^"]+)"', proxy_src))
    assert "terminal_overlay.html" in needed
    assert needed - _copied_into("/usr/local/lib/") == set()
