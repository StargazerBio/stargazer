---
sources:
  - docs/architecture/runtime.md
  - runtime/proxy.py
  - runtime/launch-notebook.sh
  - runtime/Dockerfile
  - runtime/start-local.sh
  - .github/workflows/release.yml
---

# Notebook runtime

The notebook pod beneath `docs/architecture/runtime.md`: what the code doesn't say about how a pod starts, saves and gets its image. Read it before changing anything in `runtime/`.

## Where the protocols live

The protocols are documented where they're implemented. Read those before changing any of them:

- **`runtime/proxy.py`**: hydrate, the save pass and its delete rules, the `/__sg__/*` endpoints and the data path.
- **`runtime/launch-notebook.sh`**: the SIGTERM chain, with `exec` at every hop and `--timeout-graceful-shutdown`.
- **`runtime/Dockerfile`**: the working directory, `AGENTS.md` seeding (see [[notebooks#Workspace and copies]]) and the `sg_proxy` module name.
- **`runtime/start-local.sh`**: the local entrypoint.

## Cross-cutting facts

- **On a cluster the image runs under Flyte's `fserve`**, set as the container's command. It downloads the launching app's code bundle, writes its parameters file into the working directory, then runs the launch command with `Popen(..., shell=True)`. The pod is a Flyte app (see [[flyte-apps]]) whose environment the notebook declares (see [[notebooks#main_env]]).
- **The pod manager never calls a pod.** A pod behind the login is unreachable server to server, so the pod does both ends of hydrate and save itself.
- **The save interval is fixed at launch.** The pod manager sets `SG_SAVE_INTERVAL_SECONDS` when it launches a pod (the dashboard, from the user's save-interval setting), so a running pod keeps the interval it started with.
- **The image is published per release.** `.github/workflows/release.yml` builds it for amd64 and arm64 on a calendar tag and pushes `ghcr.io/stargazerbio/stargazer:<tag>` and `:latest`. See [[images#The notebook image]].

## Related

- [[notebooks]]: what runs inside the pod
- [[storage]]: where hydrate and save read and write
- [[images]]: how the pod's image and a notebook's declared image are built
