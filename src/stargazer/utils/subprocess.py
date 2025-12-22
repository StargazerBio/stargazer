"""
Subprocess utilities for running external commands.
"""

import asyncio
from pathlib import Path
from typing import Any, Sequence


async def _run(
    cmd: Sequence[Any],
    cwd: Path | str | None = None,
) -> tuple[str, str]:
    """
    Run a command as a subprocess and capture output.

    Args:
        cmd: Command and arguments. Non-string types (Path, int, etc.) will be
             converted to strings automatically.
        cwd: Working directory for the command (optional)

    Returns:
        Tuple of (stdout, stderr) as strings

    Raises:
        RuntimeError: If the command exits with a non-zero return code
    """
    # Convert all command arguments to strings
    str_cmd = [str(arg) for arg in cmd]

    # Run the subprocess
    process = await asyncio.create_subprocess_exec(
        *str_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )

    stdout, stderr = await process.communicate()

    # Check return code and raise error if failed
    if process.returncode != 0:
        raise RuntimeError(
            f"Command {str_cmd[0]} failed with code {process.returncode}:\n"
            f"{stderr.decode('utf-8')}"
        )

    return stdout.decode("utf-8"), stderr.decode("utf-8")
