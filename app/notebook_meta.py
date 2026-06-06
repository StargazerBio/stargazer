"""
### Static parsing of a notebook's `[tool.stargazer]` resource block.

The admin app sets a per-notebook pod's resources at `/launch` time —
before the pod exists — so the resource spec has to be readable from the
notebook *source*, not from running code. Notebooks already carry a PEP
723 script header (`# /// script … # ///`) for their deps; this module
reads an optional `[tool.stargazer]` table from that same header:

    # /// script
    # dependencies = ["marimo", "stargazer"]
    #
    # [tool.stargazer]
    # cpu = 2
    # memory = "4Gi"
    # ///

Parsing is purely textual (regex + `tomllib`) — no notebook code is ever
executed. Anything missing or malformed falls back to `DEFAULT_RESOURCES`
rather than failing the launch. There is no ceiling: whatever a notebook
declares is honored as-is, so you rightsize per-notebook for the target
cluster.

spec: [docs/architecture/app.md](../docs/architecture/app.md)
"""

import re
import tomllib
from dataclasses import dataclass


# PEP 723 script-metadata block: `# /// script` … `# ///`, every line in
# between prefixed with `#`. Mirrors the reference regex in the PEP.
_PEP723_BLOCK = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s?)+)^# ///$"
)


# A single `marimo` dependency entry inside the commented header — bare
# (`"marimo"`) or already version-specified (`"marimo==0.23.6"`). Used to rewrite
# the pin; the optional spec match makes re-stamping idempotent.
_MARIMO_DEP = re.compile(
    r'(?m)^(?P<pre>#[ \t]*")marimo(?:[<>=!~][^"]*)?(?P<post>"[ \t]*,?[ \t]*)$'
)


@dataclass(frozen=True)
class NotebookResources:
    """Normalized resource request parsed from a notebook header.

    Kept separate from `flyte.Resources` so this module stays pure and
    framework-free; `app.per_notebook` converts it at launch time.
    `memory` is a Kubernetes-style quantity string (e.g. `"4Gi"`).
    """

    cpu: int
    memory: str


# Fallback only — used when a notebook declares no `[tool.stargazer]` block.
# No ceiling is applied anywhere; whatever a notebook authors is honored, so
# you rightsize per-notebook for the target cluster.
DEFAULT_RESOURCES = NotebookResources(cpu=1, memory="2Gi")


def _coerce_cpu(value: object) -> int:
    """Coerce `value` to an int cpu count, or the default if it isn't one."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_RESOURCES.cpu


def _coerce_memory(value: object) -> str:
    """Coerce a memory input to a Kubernetes quantity string.

    GiB is the fixed unit: a bare integer (the create form's number input, or
    `memory = 8` authored in a header) becomes `"<n>Gi"`. An already-suffixed
    quantity (`"4Gi"`, `"512Mi"`) passes through unchanged; empty/None falls
    back to `DEFAULT_RESOURCES.memory`.
    """
    if value is None:
        return DEFAULT_RESOURCES.memory
    text = str(value).strip()
    if not text:
        return DEFAULT_RESOURCES.memory
    return f"{text}Gi" if text.isdigit() else text


def _extract_stargazer_table(source: str) -> dict:
    """Return the `[tool.stargazer]` table from the PEP 723 header, or {}.

    Never raises: a missing block, non-`script` block, malformed TOML, or
    absent table all yield an empty dict so callers fall back to defaults.
    """
    match = _PEP723_BLOCK.search(source)
    if match is None or match.group("type") != "script":
        return {}
    content = "".join(
        line[2:] if line.startswith("# ") else line[1:]
        for line in match.group("content").splitlines(keepends=True)
    )
    try:
        meta = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return {}
    table = meta.get("tool", {}).get("stargazer", {})
    return table if isinstance(table, dict) else {}


def parse_notebook_resources(source: str) -> NotebookResources:
    """Parse `[tool.stargazer]` resources from notebook source.

    Reads `cpu` and `memory` from the PEP 723 header's `[tool.stargazer]`
    table (no ceiling — you rightsize per-notebook), filling any missing field
    from `DEFAULT_RESOURCES`. `memory` is normalized via `_coerce_memory`, so a
    bare integer is read as GiB and a suffixed quantity passes through. Always
    returns a value — never raises.
    """
    table = _extract_stargazer_table(source)
    cpu = _coerce_cpu(table["cpu"]) if "cpu" in table else DEFAULT_RESOURCES.cpu
    memory = (
        _coerce_memory(table["memory"])
        if "memory" in table
        else DEFAULT_RESOURCES.memory
    )
    return NotebookResources(cpu=cpu, memory=memory)


def resources_from_inputs(cpu: object, memory: object) -> NotebookResources:
    """Build resources from separate cpu/memory inputs (e.g. a create form).

    Values are honored as-authored — no ceiling. `cpu` is coerced to an int
    (falling back to the default if it isn't one). `memory` is a GiB count: a
    bare integer becomes `"<n>Gi"`, an already-suffixed quantity passes
    through, and empty falls back to the default (see `_coerce_memory`).
    """
    return NotebookResources(
        cpu=_coerce_cpu(cpu),
        memory=_coerce_memory(memory),
    )


def _resource_table_lines(resources: NotebookResources) -> list[str]:
    """Render the commented `[tool.stargazer]` TOML lines for a header."""
    return [
        "#",
        "# [tool.stargazer]",
        f"# cpu = {resources.cpu}",
        f'# memory = "{resources.memory}"',
    ]


def _strip_stargazer_table(body_lines: list[str]) -> list[str]:
    """Drop an existing commented `[tool.stargazer]` table from header lines.

    Skips from the `# [tool.stargazer]` line up to the next `# [..]` table
    header (or end of block), so re-injecting can't duplicate the table.
    """
    out: list[str] = []
    skipping = False
    for line in body_lines:
        inner = line.lstrip("#").strip()
        if skipping:
            if inner.startswith("[") and inner != "[tool.stargazer]":
                skipping = False
                out.append(line)
            continue
        if inner == "[tool.stargazer]":
            skipping = True
            continue
        out.append(line)
    return out


def with_pinned_marimo(source: str, version: str) -> str:
    """Return `source` with its PEP 723 `marimo` dependency pinned to `version`.

    Rewrites the `marimo` entry in the script header to `marimo=={version}`,
    whether it was bare or already pinned (idempotent). Scoped to the PEP 723
    block so a `marimo` mention elsewhere in the source is untouched. Returns
    `source` unchanged if there's no script block or no `marimo` entry — the
    create flow stamps every new notebook so the sandbox kernel matches the
    image launcher (see `app.config.MARIMO_VERSION`).
    """
    match = _PEP723_BLOCK.search(source)
    if match is None or match.group("type") != "script":
        return source
    new_block, n = _MARIMO_DEP.subn(
        rf"\g<pre>marimo=={version}\g<post>", match.group(0)
    )
    if n == 0:
        return source
    return source[: match.start()] + new_block + source[match.end() :]


def with_stargazer_resources(source: str, resources: NotebookResources) -> str:
    """Return `source` with its `[tool.stargazer]` block set to `resources`.

    Replaces an existing table or appends one before the header's closing
    `# ///`. Returns `source` unchanged if there's no PEP 723 script block
    to inject into.
    """
    match = _PEP723_BLOCK.search(source)
    if match is None or match.group("type") != "script":
        return source
    lines = match.group(0).splitlines()
    open_line, close_line, body = lines[0], lines[-1], lines[1:-1]
    body = _strip_stargazer_table(body)
    # Trim a trailing blank comment so we don't accumulate blank `#` lines.
    while body and body[-1].lstrip("#").strip() == "":
        body.pop()
    new_block = "\n".join(
        [open_line, *body, *_resource_table_lines(resources), close_line]
    )
    return source[: match.start()] + new_block + source[match.end() :]
