---
sources:
  - "[[flyte-v2-docs]]"
  - src/stargazer/config.py
---

# Flyte config

How the `flyte` CLI and SDK find the cluster they talk to. Source: [[flyte-v2-docs#Local Setup]].

## The config file

- **Three sections.** `admin` holds the endpoint (always with a `dns:///` prefix) and `insecure`; `image` holds `builder` (`local` or `remote`, see [[flyte-images]]) and optionally `registry`; `task` holds the default `org`, `project` and `domain`.
- **`flyte create config`** writes one to `./.flyte/config.yaml`; `flyte get config` shows the one in use.
- **Search order** when none is named: `./config.yaml`, `./.flyte/config.yaml`, `UCTL_CONFIG`, `FLYTECTL_CONFIG`, `~/.union/config.yaml`, `~/.flyte/config.yaml`.
- **Naming one explicitly**: `flyte --config <file>` (or `-c`) on the CLI, `flyte.init_from_config(<file>)` in the SDK.
- **Inline instead of a file**: CLI flags (`--endpoint`, `--org`, `--project`, `--domain`) or `flyte.init(endpoint=..., org=..., project=..., domain=...)`.

## In Stargazer

- **The two local configs** (`.flyte/config.yaml` for the devbox, `.flyte/union.yaml` for the tenant) and why `image.registry` stays out of them are in `AGENTS.md`.
- **The one init** is `init_flyte()` in `config.py`, whose comments say why a hosted pod inits differently.

## Related

- [[flyte]]: running tasks once initialized
