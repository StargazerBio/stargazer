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

Preconditions:

- The devbox is up, and `cli/devbox-setup.sh` has run since it was last created. Its verify step prints `✓ coredns-custom present`.
- `*.devbox.stargazer.bio` and `rustfs-svc.flyte` resolve to `127.0.0.1` on this machine (the laptop-side steps `cli/devbox-setup.sh` prints).
- `kubectl config current-context` is `flyte-devbox`.

Steps:

- **Deploy the dashboard.** Run `uv run --all-extras python cli/devbox_dashboard.py`. It ends with `Dashboard: http://dashboard-flytesnacks-development.devbox.stargazer.bio:30081`. Then `curl -s -o /dev/null -w "%{http_code}" <url>/` prints `200`, and the page shows `devbox-user` as the signed-in user. Covers `devbox-dashboard`.
- **Run the probe.** Run `uv run --all-extras python .claude/skills/verify-stargazer/scripts/devbox_storage_probe.py <tag>` with a tag not used before. It prints `read back: ['<tag>:0', '<tag>:1', '<tag>:2']` and `ok`, and exits `0`. Covers `devbox-store-index` and `devbox-assemble-fetch`.
- **Check the rows.** Run `curl -s -X POST <url>/index/query -H 'content-type: application/json' -d '{"filters": {"asset": "devbox_probe", "tag": "<tag>"}}'`. Three rows, each with a `uri` under `s3://flyte-data/stargazer/users/devbox-user/assets/` and `_owner` `devbox-user`.
- **Restart the dashboard.** Run `docker exec flyte-devbox sh -c 'kubectl delete -n flyte $(kubectl get pods -n flyte -o name | grep dashboard)'`, wait for `<url>/health` to answer `200`, and repeat the row check. The same three rows come back. Covers `devbox-index-durable`.
- **Proof.** Keep the probe's output, its run URL, and the row check from before and after the restart.

## Gotchas

- After the devbox is recreated, clear Flyte's local cache before deploying (`.opencode/reference/devbox_workarounds.md`, "Laptop-side Flyte cache"). Otherwise the deploy skips images and code bundles the wipe deleted, and the pod fails on a missing bundle.
- A deploy or run that logs `Upload failed … All connection attempts failed` couldn't reach the store: Flyte signs upload URLs for `rustfs-svc.flyte:9000`, which needs the port-forward. `cli/devbox_dashboard.py` and the probe hold one open themselves; anything else you submit needs your own.
- The dashboard image carries the project's source, so any source change since the last deploy makes the probe build it again. That takes a few seconds from cache.
- Tasks called from inside another task are submitted from that task's pod and take their image from the environment as the pod imports it. The probe passes `SG_PROBE_IMAGE` into its pods for that reason; without it, the children ran on Flyte's default image and failed with `No module named 'stargazer'`.
- Anything run in a probe pod must not import `app.admin_app`: it mounts `app/static`, which the installed package doesn't carry (`Directory '…/site-packages/app/static' does not exist`).
- The dashboard scales to zero after an hour idle. Rows survive through Litestream, but the first request after that waits for a new pod.
