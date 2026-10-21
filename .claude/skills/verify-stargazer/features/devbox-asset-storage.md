# Asset storage on the devbox

Task pods on the local devbox store files as assets and find them again from other pods, the way they do on Union. Bytes go to the devbox's object store (rustfs, bucket `flyte-data`) under `stargazer/users/devbox-user/assets/<cid>/<name>`. Rows go to the asset index, a Postgres server in the `stargazer` namespace on its own volume, which pods and the dashboard reach directly. The dashboard opens in a browser as a stand-in user, `devbox-user`, and its asset browser lists what pods stored.

## Sub-features

- `devbox-dashboard` deploys the dashboard on the devbox with `devbox/dashboard.py` and serves it as the stand-in user.
- `devbox-store-index` stores files from one pod and indexes them in the devbox's Postgres.
- `devbox-assemble-fetch` finds those files from a second pod with `assemble()` and reads them back with `fetch()`.
- `devbox-dashboard-assets` lists those files in the dashboard's asset browser, which reads the same index.
- `devbox-index-durable` keeps the index through a restart of the Postgres pod.
- `devbox-typed-extras` keeps a typed asset's extra keyvalues (an `R1` tagged `lane`) through a task handoff and an `assemble()` from another pod.

## How to get to it (user POV)

- After `flyte start devbox`, run `devbox/setup.sh`, which also starts the index's Postgres server. Then `uv run --all-extras python devbox/dashboard.py` prints the dashboard's URL, `http://dashboard-flytesnacks-development.devbox.stargazer.bio:30081`.
- Runs submitted from your machine store into the devbox when these are exported: `STARGAZER_STORE_ROOT=s3://flyte-data/stargazer`, `STARGAZER_INDEX_URL=postgresql://stargazer:stargazer@postgres.stargazer.svc.cluster.local:5432/stargazer`, `STARGAZER_OWNER=devbox-user`. Keep `kubectl port-forward -n flyte svc/rustfs-svc 9000:9000` open while submitting, so the code bundle can upload.

## Driving it

Driven by the devbox test tier, `tests/devbox/`. The session deploys the dashboard itself, passes the devbox storage settings to every run, and reads the index through a port-forward to the Postgres service, so nothing needs exporting first.

Preconditions:

- The devbox is up, and `devbox/setup.sh` has run since it was last created. Its verify step prints `✓ coredns-custom present`, `✓ PINATA_JWT secret present` and `✓ Postgres ready`.
- `*.devbox.stargazer.bio` and `rustfs-svc.flyte` resolve to `127.0.0.1` on this machine (the steps for this machine that `devbox/setup.sh` prints).
- `kubectl config current-context` is `flyte-devbox`.

Steps:

- **Run the tests.** Run `uv run --all-extras pytest -m devbox -rP tests/devbox/test_dashboard.py tests/devbox/test_asset_storage.py`. Six tests pass and it exits `0`:
  - `test_dashboard_serves_the_stand_in_user` covers `devbox-dashboard`: the deployed dashboard answers `200` and shows `devbox-user`.
  - `test_read_back_from_another_pod` covers `devbox-store-index` and `devbox-assemble-fetch`: one pod stores three files under a fresh tag, a second finds them with `assemble()` and reads each back.
  - `test_indexed_in_postgres`: one row per file in the devbox's Postgres, at `s3://flyte-data/stargazer/users/devbox-user/assets/<cid>/<name>`, with `_owner` `devbox-user`.
  - `test_dashboard_lists_the_rows` covers `devbox-dashboard-assets`: the dashboard's private asset list for the tag names the three files.
  - `test_extra_keyvalue_travels_between_pods` covers `devbox-typed-extras`: one pod stores an `R1` with an extra `lane` key and returns it, and the next pod gets it as an input and also finds it with `assemble(lane=...)`. Both copies are `R1`s carrying `lane`; the found one also carries the stamped `_owner`.
  - `test_index_survives_a_postgres_restart` covers `devbox-index-durable`: it deletes the Postgres pod, waits until the index answers again, and gets the same rows back.
- **Proof.** Keep the pytest output. `-rP` prints each run's URL.

## Gotchas

- `devbox/setup.sh` also clears Flyte's local cache in every checkout, so run it after the devbox is recreated, before the first deploy. Otherwise the deploy skips images and code bundles the wipe deleted, and the pod fails on a missing bundle.
- A deploy or run that logs `Upload failed … All connection attempts failed` couldn't reach the store: Flyte signs upload URLs for `rustfs-svc.flyte:9000`, which needs the port-forward. The tests hold one open; anything else you submit needs your own.
- The dashboard and the task image carry the project's source, so any source change since the last session builds them again first.
- What runs in the tests' pods lives in `tests/devbox/pod_tasks.py` and must import only what `gatk_env`'s image carries. Importing `app.admin_app` there fails: it mounts `app/static`, which the installed package doesn't carry.
- The dashboard scales to zero after an hour idle; the first request after that waits for a new pod. The index isn't on the dashboard, so runs never wait for it.
- Right after a redeploy, Knative can route a request to the previous revision for a few seconds, waking it if it had scaled to zero. A dashboard test that depends on what the new revision changed can fail on that one request; the pod's log names its revision. Run it again.
