# Devbox

The local Flyte devbox's own setup. Run it from the repo root.

## setup.sh

Readies a fresh `flyte-devbox` container for Stargazer. Its header lists the steps and what the devbox can't fix, and each step's reason is in the comments above it. The changes are lost whenever the container is recreated, so re-run it after every fresh devbox. It's safe to re-run.

```bash
devbox/setup.sh [--dry-run] [--laptop] [--verify-pod]
```

`--laptop` also applies the macOS DNS change (needs sudo); without it, the script prints the commands. `--verify-pod` checks from a throwaway pod that the devbox dashboard resolves and answers in-cluster (the dashboard deploys from the infra repo's `devbox/dashboard.py`).

Recreating the devbox wipes its registry and store, so the script also clears Flyte's local cache in every checkout of this repo, and of an infra checkout when `INFRA_CHECKOUT` names one.

It applies two files from this folder:

- `coredns-custom.yaml`: the CoreDNS wildcard, with the node's IP filled in.
- `postgres.yaml`: the asset index's Postgres server.
