---
sources:
  - "[[flyte-v2-docs]]"
  - "[[flyte-sdk-examples]]"
  - src/stargazer/config.py
---

# Flyte config

How the `flyte` CLI and SDK find the cluster they talk to. Source: [[flyte-v2-docs#Local Setup]].

## The config file

- **Three sections.** `admin` holds the endpoint (always with a `dns:///` prefix) and `insecure`; `image` holds `builder` (`local` or `remote`, see [[images]]) and optionally `registry`; `task` holds the default `org`, `project` and `domain`.
- **`flyte create config`** writes one to `./.flyte/config.yaml`; `flyte get config` shows the one in use.
- **Search order** when none is named: `./config.yaml`, `./.flyte/config.yaml`, `UCTL_CONFIG`, `FLYTECTL_CONFIG`, `~/.union/config.yaml`, `~/.flyte/config.yaml`.
- **Naming one explicitly**: `flyte --config <file>` (or `-c`) on the CLI, `flyte.init_from_config(<file>)` in the SDK.
- **Inline instead of a file**: CLI flags (`--endpoint`, `--org`, `--project`, `--domain`) or `flyte.init(endpoint=..., org=..., project=..., domain=...)`.

## In Stargazer

- **Two local configs, both gitignored.** `.flyte/config.yaml` points at the devbox and `.flyte/union.yaml` at the Union tenant, which every tenant command names with `--config`. A worktree links both from the main checkout.
- **Never set `image.registry` in the file.** Flyte reads it when an image is defined, so it would leak into a Union run from the same checkout. The devbox exports `FLYTE_IMAGE_REGISTRY` instead. See [[images#Stargazer's quirks]].
- **`init_flyte()` is the one init.** In a hosted notebook pod (`_U_EP_OVERRIDE` set) it calls `flyte.init_in_cluster` from the SDK's own directory, because `init_in_cluster` takes the code bundle's root from the working directory and a pod's is the workspace. Anywhere else it calls `flyte.init_from_config()`.

## Related

- [[flyte]]: running tasks once initialized
