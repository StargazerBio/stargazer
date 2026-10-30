# Notebook Runtime — Internals (agent reference)

The companion to the human-facing [docs/architecture/runtime.md](../../../docs/architecture/runtime.md). The protocols themselves are documented where they're implemented: hydrate, the save pass and its delete rules, the `/__sg__/*` endpoints and the data path in `runtime/proxy.py`; the SIGTERM chain (`exec` at every hop, `--timeout-graceful-shutdown`) in `runtime/launch-notebook.sh`; the working directory, `AGENTS.md` seeding and the `sg_proxy` module name in `runtime/Dockerfile`; the local entrypoint in `runtime/start-local.sh`. Read those before changing any of them. This file holds what they don't.

## Cross-cutting facts

- On a cluster the image runs under Flyte's `fserve`, set as the container's command: it downloads the launching app's code bundle, writes its parameters file into the working directory, then runs the launch command with `Popen(..., shell=True)`.
- The pod manager never calls a pod (a pod behind the login is unreachable server-to-server), so the pod does both ends of hydrate and save itself. The pod manager sets `SG_SAVE_INTERVAL_SECONDS` at launch (the dashboard from the user's save-interval setting), so a running pod keeps the interval it started with.
- `.github/workflows/release.yml` builds the image for amd64 and arm64 on a calendar tag and pushes `ghcr.io/stargazerbio/stargazer:<tag>` and `:latest`. Union's nodes pull it from GHCR, which is public. A notebook's declared image (`main_env`) is built on top of it by Union's remote builder in the owner's project.
