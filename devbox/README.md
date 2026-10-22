# Devbox

The local Flyte devbox's own infrastructure. Run these from the repo root.

## setup.sh

Readies a fresh `flyte-devbox` container for Stargazer. Its header lists the
steps and what the devbox can't fix. The changes are lost whenever the
container is recreated, so re-run it after every fresh devbox. It's safe to
re-run.

```bash
devbox/setup.sh [--dry-run] [--laptop] [--verify-pod]
```

`--laptop` also applies the macOS DNS change (needs sudo); without it, the
script prints the commands. `--verify-pod` checks from a throwaway pod that
the devbox dashboard resolves and answers in-cluster. `--help` prints the
header, which also lists what the devbox can't do. Each step's reason is in
the comments above it.

It applies two files from this folder:

- `coredns-custom.yaml`: the CoreDNS wildcard, with the node's IP filled in.
- `postgres.yaml`: the asset index's Postgres server.

## dashboard.py

Deploys a dashboard on the devbox, after `setup.sh`. The devbox has no Union
users or login, so it's one dashboard in the default project for a stand-in
user, `devbox-user`, storing under the devbox's bucket. It refuses to run
unless `STARGAZER_TARGET=devbox` (the default), and prints the dashboard's
URL.

```bash
uv run --all-extras python devbox/dashboard.py
```

Its docstring says what each setting is for, and how to send runs' assets to
the devbox without it.
