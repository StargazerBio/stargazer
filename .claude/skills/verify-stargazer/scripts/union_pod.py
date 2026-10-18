"""Drive the Union test account's dashboard and notebook pods without a browser.

Calls go out as the Flyte CLI's signed-in user, whose bearer token passes the
platform login on both the dashboard and the pods. Run from the checkout root.

    union_pod.py create <name>         # a workspace notebook from the blank seed
    union_pod.py launch <slug>         # Edit mode; prints the pod's URL
    union_pod.py stop <slug>           # deactivate it (the pod gets SIGTERM)
    union_pod.py ready <url>           # wait until the pod serves
    union_pod.py status <url>          # its save status (files too big to save)
    union_pod.py sh <url> '<command>'  # run a command in its terminal
    union_pod.py store <url>           # list the owner's stored workspace

`sh` and `store` use the pod's own dropdown-terminal websocket. Its login
shell's `python` lacks `flyte`; the base image's is `/opt/venv/bin/python`.
"""

import asyncio
import base64
import json
import re
import sys
import time
import uuid

import httpx
import websockets
from flyte.remote._client.auth._keyring import KeyringStore

HOST = "stargazerbio.us-west-2.unionai.cloud"
DASHBOARD = "https://u-pryce.apps.stargazerbio.us-west-2.unionai.cloud"
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\r")
# Lists the owner's stored workspace the way the proxy reads it.
_STORE_LS = """
import sg_proxy as p
import flyte.storage as s

p._init_storage()
pre = p._user_prefix("workspace")
fs = s.get_underlying_filesystem(path=pre)
base = fs._strip_protocol(pre).rstrip("/") + "/"
for path in sorted(fs.find(pre)):
    print(path.removeprefix(base), fs.size(path))
"""


def _token() -> str:
    """The CLI's access token for the tenant."""
    return KeyringStore.retrieve(HOST).access_token


def _client() -> httpx.Client:
    """An HTTP client that passes the platform login."""
    return httpx.Client(
        headers={"Authorization": f"Bearer {_token()}", "Accept": "application/json"},
        timeout=900,
    )


async def _sh(url: str, command: str) -> str:
    """Run `command` in the pod's login shell; return what it printed."""
    marker = f"__done_{uuid.uuid4().hex[:8]}__"
    ws_url = url.replace("https://", "wss://").rstrip("/") + "/__sg__/term"
    async with websockets.connect(
        ws_url,
        additional_headers={"Authorization": f"Bearer {_token()}"},
        max_size=None,
    ) as ws:
        await ws.send(json.dumps({"type": "resize", "rows": 50, "cols": 250}))
        for line in ("stty -echo; export PS1=''", command, f"echo {marker}"):
            await ws.send(json.dumps({"type": "input", "data": line + "\n"}))
        out = ""
        async with asyncio.timeout(600):
            # The PTY may echo the typed lines; the printed marker comes last.
            while marker not in out.rsplit("echo " + marker, 1)[-1]:
                frame = await ws.recv()
                out += (
                    frame.decode(errors="replace")
                    if isinstance(frame, bytes)
                    else frame
                )
    # Drop what came before the shell went quiet: the prompt, and the typed
    # lines if the PTY echoed them.
    text = _ANSI.sub("", out).rsplit("export PS1=''", 1)[-1]
    text = text.rsplit("echo " + marker, 1)[-1]
    return text.split(marker)[0].strip()


def main() -> None:
    """Dispatch one subcommand and print its result."""
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "sh":
        print(asyncio.run(_sh(arg, sys.argv[3])))
        return
    if cmd == "store":
        script = base64.b64encode(_STORE_LS.encode()).decode()
        print(
            asyncio.run(
                _sh(
                    arg,
                    f"echo {script} | base64 -d > /tmp/store_ls.py && "
                    "/opt/venv/bin/python /tmp/store_ls.py 2>&1",
                )
            )
        )
        return
    with _client() as c:
        if cmd == "create":
            r = c.post(f"{DASHBOARD}/workspace/create", data={"name": arg})
            print(r.status_code, r.json().get("slug", r.text[:200]))
        elif cmd == "launch":
            r = c.post(
                f"{DASHBOARD}/launch",
                data={"slug": arg, "mode": "edit", "section": "workspace"},
            )
            print(r.status_code, r.json().get("url", r.text[:200]))
        elif cmd == "stop":
            r = c.post(f"{DASHBOARD}/stop", data={"slug": arg, "mode": "edit"})
            print(r.status_code, r.text[:200])
        elif cmd == "ready":
            deadline = time.monotonic() + 900
            while time.monotonic() < deadline:
                try:
                    if c.get(f"{arg}/__sg__/ready", timeout=30).status_code == 200:
                        print("ready")
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(10)
            sys.exit("not ready after 15 minutes")
        elif cmd == "status":
            print(json.dumps(c.get(f"{arg}/__sg__/save-status").json()))
        else:
            sys.exit(f"unknown command: {cmd}")


if __name__ == "__main__":
    main()
