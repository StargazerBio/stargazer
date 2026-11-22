"""The MCP server over stdio: stdout is the transport, so nothing but
JSON-RPC may reach it, whatever the server logs on its way up.
"""

import json
import subprocess
import sys

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}


def test_first_stdout_line_is_the_initialize_reply():
    """The server's first line on stdout is its reply to `initialize`."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "stargazer.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        proc.stdin.write(json.dumps(INITIALIZE) + "\n")
        proc.stdin.flush()
        first = proc.stdout.readline()
    finally:
        proc.kill()
        proc.wait()
    assert json.loads(first)["id"] == 1
