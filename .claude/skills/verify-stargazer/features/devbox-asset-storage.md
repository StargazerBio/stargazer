# Asset storage on the devbox

Task pods on the local devbox store files as assets and find them again from other pods, the way they do on Union. Bytes go to the devbox's object store (rustfs, bucket `flyte-data`) under `stargazer/users/devbox-user/assets/<cid>/<name>`. Rows go to the asset index held by the devbox dashboard, which pods reach at its in-cluster address and which Litestream keeps in the same bucket. The dashboard itself opens in a browser as a stand-in user, `devbox-user`.

## Sub-features

- `devbox-dashboard` deploys the dashboard on the devbox with `cli/devbox_dashboard.py` and serves it as the stand-in user.
- `devbox-store-index` stores files from one pod and indexes them through the dashboard.
- `devbox-assemble-fetch` finds those files from a second pod with `assemble()` and reads them back with `fetch()`.
- `devbox-index-durable` restores the index after the dashboard pod restarts.

## How to get to it (user POV)

- After `flyte start devbox` and `cli/devbox-setup.sh`, run `uv run --all-extras python cli/devbox_dashboard.py`. It prints the dashboard's URL, `http://dashboard-flytesnacks-development.devbox.stargazer.bio:30081`.
- Runs submitted from your machine store into the devbox when these are exported: `STARGAZER_STORE_ROOT=s3://flyte-data/stargazer`, `STARGAZER_INDEX_URL=http://dashboard-flytesnacks-development.flyte.svc.cluster.local`, `STARGAZER_OWNER=devbox-user`. Keep `kubectl port-forward -n flyte svc/rustfs-svc 9000:9000` open while submitting, so the code bundle can upload.

## Driving it

Driven by the devbox test tier, `tests/devbox/`. The session deploys the dashboard itself and passes the devbox storage settings to every run, so nothing needs exporting first.

Preconditions:

- The devbox is up, and `cli/devbox-setup.sh` has run since it was last created. Its verify step prints `✓ coredns-custom present` and `✓ PINATA_JWT secret present`.
- `*.devbox.stargazer.bio` and `rustfs-svc.flyte` resolve to `127.0.0.1` on this machine (the steps for this machine that `cli/devbox-setup.sh` prints).
- `kubectl config current-context` is `flyte-devbox`.

Steps:

- **Run the tests.** Run `uv run --all-extras pytest -m devbox -rP tests/devbox/test_dashboard.py tests/devbox/test_asset_storage.py`. Four tests pass and it exits `0`:
  - `test_dashboard_serves_the_stand_in_user` covers `devbox-dashboard`: the deployed dashboard answers `200` and shows `devbox-user`.
  - `test_read_back_from_another_pod` covers `devbox-store-index` and `devbox-assemble-fetch`: one pod stores three files under a fresh tag, a second finds them with `assemble()` and reads each back.
  - `test_indexed_by_the_dashboard`: one index row per file, at `s3://flyte-data/stargazer/users/devbox-user/assets/<cid>/<name>`, with `_owner` `devbox-user`.
  - `test_index_survives_a_dashboard_restart` covers `devbox-index-durable`: it deletes the dashboard's pod, waits for `/health`, and gets the same rows back.
- **Proof.** Keep the pytest output. `-rP` prints each run's URL.

## Gotchas

- After the devbox is recreated, clear Flyte's local cache before the first run (`.opencode/reference/devbox_workarounds.md`, "Laptop-side Flyte cache"). Otherwise the deploy skips images and code bundles the wipe deleted, and the pod fails on a missing bundle.
- A deploy or run that logs `Upload failed … All connection attempts failed` couldn't reach the store: Flyte signs upload URLs for `rustfs-svc.flyte:9000`, which needs the port-forward. The tests hold one open; anything else you submit needs your own.
- The dashboard and the task image carry the project's source, so any source change since the last session builds them again first.
- What runs in the tests' pods lives in `tests/devbox/pod_tasks.py` and must import only what `gatk_env`'s image carries. Importing `app.admin_app` there fails: it mounts `app/static`, which the installed package doesn't carry.
- The dashboard scales to zero after an hour idle. Rows survive through Litestream, but the first request after that waits for a new pod.
