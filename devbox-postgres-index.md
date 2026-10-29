---
title: devbox-postgres-index
status: done
priority: high
created: 2026-10-20
pr: 60
---

The second of three steps toward the hosted index on Aurora DSQL (ticket
`dsql-asset-index`). The devbox's index moves from the stand-in user's
dashboard to a Postgres deployment, reached by task and notebook pods
through `PostgresIndex` (ticket `postgres-index`).

- [x] A Postgres deployment in `cli/devbox-setup.sh`, and its entry in
  `devbox_workarounds.md`
- [x] The devbox dashboard and runs get the Postgres `STARGAZER_INDEX_URL`
  (`tests/devbox/conftest.py`, `contributing.md`'s devbox recipe)
- [x] The devbox asset-storage and germline tests pass on it
- [x] The `postgres` tier can run against the devbox's Postgres as well as a
  local container, if that turns out useful: it doesn't. The tier's `index`
  fixture drops the `assets` table before every test, so it would wipe the
  devbox's index, and it would test the same `postgres:16-alpine` engine

Union keeps the dashboard-served index until `dsql-asset-index`, so nothing
is removed here.

## Verified (2026-10-20, branch `feat/devbox-postgres-index`)

- **Before:** with no Postgres deployed, the new storage test's pod failed
  with `failed to resolve host 'postgres.stargazer.svc.cluster.local'`.
- **`cli/devbox-setup.sh`:** exit 0 in 21 s, `✓ Postgres ready`; a second
  run left all four objects `unchanged`. The pod uses 53 MiB idle (256 MiB
  limit), PostgreSQL 16.15.
- **Devbox tier:** 8 passed (`pytest -m devbox -rP tests/devbox`, commit
  `82da062`, 2:33), including the germline workflow. The first run, on the
  switch-over deploy, failed `test_dashboard_lists_the_rows` once because
  Knative routed that request to the previous dashboard revision (still on
  SQLite).
- **Rows in Postgres:** every germline output, under
  `s3://flyte-data/stargazer/users/devbox-user/assets/`.
- **A notebook pod** launched from the devbox dashboard got the Postgres URL,
  and its sandbox Python read the task pods' `variants` rows through
  `PostgresIndex`.
- **Postgres tier:** 10 passed. **Unit tier:** 505 passed.

## Outcome

Merged as #60. The devbox's index is a Postgres deployment
(`devbox/postgres.yaml`, applied by `devbox/setup.sh`), and the devbox
dashboard, its notebook pods and devbox runs all use it through
`PostgresIndex`. Before merge the devbox infra moved from `cli/` to
`devbox/`, and `devbox_workarounds.md` was folded into `devbox/setup.sh`'s
commented steps. Verified as above: devbox tier 8 passed, postgres tier 10,
unit 505. Left: the dashboard-served index (`HttpIndex`, the `/index` routes,
Litestream) still runs on Union, and goes in ticket `dsql-asset-index`.

## Verification recipe: Asset storage on the devbox

Task pods on the local devbox store files as assets and find them again from other pods, the way they do on Union. Bytes go to the devbox's object store (rustfs, bucket `flyte-data`) under `stargazer/users/devbox-user/assets/<cid>/<name>`. Rows go to the asset index, a Postgres server in the `stargazer` namespace on its own volume, which pods and the dashboard reach directly. The dashboard opens in a browser as a stand-in user, `devbox-user`, and its asset browser lists what pods stored.

### Sub-features

- `devbox-dashboard` deploys the dashboard on the devbox with `devbox/dashboard.py` and serves it as the stand-in user.
- `devbox-store-index` stores files from one pod and indexes them in the devbox's Postgres.
- `devbox-assemble-fetch` finds those files from a second pod with `assemble()` and reads them back with `fetch()`.
- `devbox-dashboard-assets` lists those files in the dashboard's asset browser, which reads the same index.
- `devbox-index-durable` keeps the index through a restart of the Postgres pod.
- `devbox-typed-extras` keeps a typed asset's extra keyvalues (an `R1` tagged `lane`) through a task handoff and an `assemble()` from another pod.

### How to get to it (user POV)

- After `flyte start devbox`, run `devbox/setup.sh`, which also starts the index's Postgres server. Then `uv run --all-extras python devbox/dashboard.py` prints the dashboard's URL, `http://dashboard-flytesnacks-development.devbox.stargazer.bio:30081`.
- Runs submitted from your machine store into the devbox when these are exported: `STARGAZER_STORE_ROOT=s3://flyte-data/stargazer`, `STARGAZER_INDEX_URL=postgresql://stargazer:stargazer@postgres.stargazer.svc.cluster.local:5432/stargazer`, `STARGAZER_OWNER=devbox-user`. Keep `kubectl port-forward -n flyte svc/rustfs-svc 9000:9000` open while submitting, so the code bundle can upload.

### Driving it

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

### Gotchas

- `devbox/setup.sh` also clears Flyte's local cache in every checkout, so run it after the devbox is recreated, before the first deploy. Otherwise the deploy skips images and code bundles the wipe deleted, and the pod fails on a missing bundle.
- A deploy or run that logs `Upload failed … All connection attempts failed` couldn't reach the store: Flyte signs upload URLs for `rustfs-svc.flyte:9000`, which needs the port-forward. The tests hold one open; anything else you submit needs your own.
- The dashboard and the task image carry the project's source, so any source change since the last session builds them again first.
- What runs in the tests' pods lives in `tests/devbox/pod_tasks.py` and must import only what `gatk_env`'s image carries. Importing `app.admin_app` there fails: it mounts `app/static`, which the installed package doesn't carry.
- The dashboard scales to zero after an hour idle; the first request after that waits for a new pod. The index isn't on the dashboard, so runs never wait for it.
- Right after a redeploy, Knative can route a request to the previous revision for a few seconds, waking it if it had scaled to zero. A dashboard test that depends on what the new revision changed can fail on that one request; the pod's log names its revision. Run it again.

## Verification recipe: Germline variant calling on the devbox

`germline_short_variant_discovery` runs on the local devbox the way it runs on Union, with every step in its own pod. Given a reference and one sample's paired reads in the asset store, it indexes the reference, aligns the reads with bwa-mem2, sorts and marks duplicates, calls the sample's GVCF with HaplotypeCaller, and joint-genotypes the cohort. Each output is stored as an asset, and the cohort's VCF can be found from any pod with `assemble()`.

### Sub-features

- `devbox-germline-seed` stores the TP53 reference and NA12829's paired reads from a pod.
- `devbox-germline-run` runs the workflow from SDK code on this machine (`init_flyte()` from the repo root, then `flyte.run(...)`), each step in a pod on `gatk_env`'s image.
- `devbox-germline-joint-call` joint-genotypes over every contig in the reference, through GenomicsDB, which runs only on x86_64.
- `devbox-germline-output` finds the cohort's VCF from another pod and reads it back.

### How to get to it (user POV)

- With the devbox up and `devbox/setup.sh` applied (see the asset storage recipe above), export the three devbox storage settings and keep the store port-forward open, as in `docs/guides/contributing.md` → Running on the Devbox.
- Store a reference with `build` set and a sample's R1 and R2 under one `sample_id`, then call `flyte.run(germline_short_variant_discovery, build=..., sample_ids=[...], cohort_id=...)`.

### Driving it

Driven by the devbox test tier, `tests/devbox/test_germline.py`. The session passes the devbox storage settings to every run, so nothing needs exporting first, and these tests don't need the dashboard.

Preconditions: the same as the asset storage recipe above.

Steps:

- **Run the tests.** Run `uv run --all-extras pytest -m devbox -rP tests/devbox/test_germline.py`. Both tests pass and it exits `0`. Their shared setup seeds the TP53 reference and NA12829's reads from a pod (`devbox-germline-seed`), then runs the workflow for a fresh cohort, which has to succeed (`devbox-germline-run`).
  - `test_workflow_joint_calls_the_cohort` covers `devbox-germline-joint-call`: the workflow returns a VCF from `joint_call_gvcfs` for the cohort, built from `NA12829` on `GRCh38`.
  - `test_cohort_vcf_found_from_another_pod` covers `devbox-germline-output`: another pod finds the VCF by cohort, and it holds sample `NA12829`, contig `chr17:7658421-7697490`, and at least one record.
- **Proof.** Keep the pytest output. `-rP` prints each run's URL. With the images already built, the workflow run takes about a minute and a half (1m26s measured).

### Gotchas

- Every Stargazer image is built for x86_64 only. On Apple silicon the devbox runs natively and these pods run emulated, which is slower than Union. Don't start the devbox itself as x86_64: no pod ever starts (the header of `devbox/setup.sh`).
- The first run after a source change builds the GATK image under emulation. When only the source changed, that's the project's install layer; a recipe change rebuilds more.
- The tests bundle code from the repo root, as SDK code does by default. Their pods import `tests.devbox.pod_tasks` from the bundle and `stargazer` from the image.
- `devbox/setup.sh` clears Flyte's local cache, so run it after the devbox is recreated, before the first run. Each session seeds again, so the store and index needn't survive.
- A run with no `PINATA_JWT` secret on the devbox fails before any pod starts, with `none of the secret managers injected secret`. `devbox/setup.sh` creates it.
