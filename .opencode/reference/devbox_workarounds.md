# Devbox Workarounds

`cr.flyte.org/flyteorg/flyte-devbox` is the local Flyte v2 dev cluster (k3s + flyte-binary + rustfs + knative + docker-registry inside one Docker container). Most behavior matches a production Flyte deploy, but several quirks bite us on every deploy iteration. This file is the running ledger of those quirks and how to step around them.

When you hit a deploy/runtime issue against devbox that takes more than one round-trip to diagnose, append it here with a one-line description and the minimum the next session needs to know.

**Automation:** the *cluster-side* workarounds below (signed-URL endpoint, serving domain off `.localhost`, CoreDNS wildcard, the restarts that race the addon controller, and the `PINATA_JWT` task secret) are applied to a fresh devbox by [`cli/devbox-setup.sh`](../../cli/devbox-setup.sh) — run it once after recreating the container (`./cli/devbox-setup.sh`, or `--dry-run` to preview, `--laptop` to also apply the macOS DNS steps, `--domain` to override). It's idempotent; `--verify-pod` also resolves and calls the devbox dashboard from a throwaway pod. The remaining entries are app-code/design (already in the codebase), not scriptable; keep this file and the script in sync when you add a new cluster-side quirk.

---

## Stargazer pods run x86_64 on an arm64 devbox

**Symptom:** On a multi-arch build, `joint_call_gvcfs` fails in GenomicsDBImport with `Could not load genomicsdb native library`, while every other germline step succeeds (measured 2026-10-08, run `rq67nc297wm8x45tg6cd`).

**Cause:** On Apple silicon `flyte start devbox` pulls the devbox image's arm64 variant, so the k3s node is arm64 and pods got the arm64 side of Stargazer's images. GATK 4.6.2's GenomicsDB native library ships for x86_64 only. Union's nodes are x86_64.

**An x86_64 devbox doesn't work.** `DOCKER_DEFAULT_PLATFORM=linux/amd64 flyte start devbox` starts the container as x86_64 under Rosetta, but no pod ever starts: every sandbox fails with `failed to generate seccomp spec opts: seccomp is not supported` (measured 2026-10-08). k3s's containerd and runc are then x86_64 binaries under emulation, and the emulator refuses to install seccomp filters.

**Fix (in code):** Stargazer's images are built for `linux/amd64` only (`IMAGE_PLATFORM` in `src/stargazer/config.py`), and the arm64 node runs those pods under Docker Desktop's emulation (measured: a pod on an amd64-only image prints `x86_64`). The pull is the catch: buildx attaches a provenance attestation by default, which makes even a one-platform push an index, and the node refuses it with `no match for platform in manifest: not found` (measured). `stargazer.config` sets `FLYTE_DOCKER_BUILD_EXTRA_ARGS=--provenance=false` on the devbox target, so the push is a plain image the node pulls whatever its architecture. Flyte's own images (flyte-binary, Knative, the devbox plumbing) stay native.

---

## Storage signed URLs use `localhost`

**Symptom:** Inside any App pod, `flyte.serve.aio(env)` (or any code-bundle upload) fails with `All connection attempts failed` on `http://localhost:30002/flyte-data/...`.

**Cause:** `flyte-binary-config` has `signedURL.endpoint: http://localhost:30002`. The control plane returns signed upload URLs with that host. Pods see `localhost` as their own loopback — nothing is listening there.

There is no single host/IP that's reachable from both the laptop and from in-cluster pods on macOS Docker Desktop (node IPs aren't routable from the host VM, `localhost` is the pod loopback). The fix targets pods (production parity) and pays a dev-machine cost on the laptop.

**Workaround:**

1. Patch the source manifest inside the devbox container (the `flyte-binary-config` configmap is owned by a k3s Addon controller, so `kubectl patch` reverts):

   ```bash
   docker exec flyte-devbox sed -i \
     's|endpoint: http://localhost:30002|endpoint: http://rustfs-svc.flyte:9000|' \
     /var/lib/rancher/k3s/server/manifests/flyte.yaml
   kubectl rollout restart deployment/flyte-binary -n flyte
   ```

   Pods now resolve `rustfs-svc.flyte:9000` via k8s DNS — same code path as a production Flyte that returns real S3 URLs.

2. On the laptop, make `rustfs-svc.flyte:9000` resolvable:
   - DNS / `/etc/hosts`: `rustfs-svc.flyte → 127.0.0.1`
   - Port-forward: `kubectl port-forward -n flyte svc/rustfs-svc 9000:9000`

   `cli/devbox_dashboard.py` holds the port-forward open while it deploys (reusing one already listening on :9000), and so do the devbox tests (`pytest -m devbox`). Anything else that uploads from the laptop, such as a `flyte.run` against the devbox, needs the forward running: without it the code-bundle upload logs `Upload failed … ConnectError: All connection attempts failed` (measured 2026-10-08).

---

## Task pods are rejected without the `PINATA_JWT` secret

**Symptom:** Every `gatk_env` or `scrna_env` run fails at once, before a pod starts: `admission webhook "flyte-pod-webhook.flyte.org" denied the request: none of the secret managers injected secret [key:"PINATA_JWT" …]` (measured 2026-10-08).

**Cause:** Both task environments declare `secrets=[flyte.Secret(key="PINATA_JWT")]` (`STARGAZER_SECRETS` in `src/stargazer/config.py`), and the pod webhook refuses a pod whose declared secret doesn't exist. Union has it as an org-wide secret; a fresh devbox has no secrets at all. Flyte has no optional secrets.

**Fix (automated):** `cli/devbox-setup.sh` creates it, org-wide like Union's, from `$PINATA_JWT` or else the repo's `.env`. With neither it creates it empty, which schedules the pods and leaves them without the public tier. It replaces any existing one, so re-running picks up a changed key.

---

## `AppEnvironment(secrets=[...])` is silently dropped

**Symptom:** Secret registered with `flyte create secret`, declared on the `AppEnvironment` via `secrets=[flyte.Secret(...)]`, never reaches the running container. `os.environ["MY_SECRET"]` raises `KeyError`.

**Cause:** `secrets=[...]` is dropped at the flyte-binary → Knative translation — **not** merely the missing label. Verified by deploying an AppEnvironment with `secrets=[flyte.Secret(...)]` and inspecting the rendered ksvc: `kubectl get ksvc <app> -n flyte -o jsonpath='{.spec.template.metadata.annotations}'` shows only `autoscaling.knative.dev/*` — no secret annotations and no `inject-flyte-secrets` label. The `flyte-binary-webhook` (`failurePolicy: Fail`, `objectSelector matchLabels: inject-flyte-secrets=true`) injects from pod *annotations*, so with neither annotation nor label present **no cluster-side webhook change can rescue it** — there is nothing for the webhook to act on. This is a Flyte App-serving limitation, reproducible on any cluster, not a pure devbox quirk.

**Workaround:** Bake secret values into `env_vars={...}` from the deployer's local shell at deploy time, e.g. `env_vars={"MY_SECRET": os.environ["MY_SECRET"]}`.

**The app tier bakes no secrets today.** Plan 25 removed the GitHub OAuth, GitHub App and session secrets, and plan 26 stopped baking `PINATA_JWT` into dashboards: a user can read their own dashboard's app spec, so any secret there reaches that user. A secret the app tier needs again has to come from real secret injection, or be one each user may see.

**Trade-off / prod gap:** secret values are stored in the App spec in Flyte's DB. This is the one accepted parity gap in `app/` — revisit when Flyte supports App-pod secret injection (then switch to `secrets=[flyte.Secret(key=…, as_env_var=…)]` and drop the baking).

Paths investigated and rejected: (a) `pod_template=PodTemplate(labels={"inject-flyte-secrets": "true"})` — even with the label the webhook has no secret annotations to inject, because flyte-binary never stamps them on App pods; (b) relaxing the webhook `objectSelector` — same reason, and `failurePolicy: Fail` makes a match-all selector dangerous (a webhook blip would block all pod scheduling).

---

## App pods get `rustfs.flyte` as the store address (fixed upstream)

> **Fixed upstream:** the devbox image now ships the right service name, so `cli/devbox-setup.sh` no longer patches it; its verify step warns if a bare `rustfs.flyte:9000` comes back. Kept so a regression is recognizable.

**Symptom:** App pod crash-loops before user code runs, logs show `GenericError: Generic S3 error ... http://rustfs.flyte:9000/... Name or service not known`.

**Cause:** `/var/lib/rancher/k3s/server/manifests/flyte.yaml` (line ~7776) sets `internalApps.defaultEnvVars.FLYTE_AWS_ENDPOINT = http://rustfs.flyte:9000`. The actual k8s service is `rustfs-svc`. (The `plugins.k8s.default-env-vars` block uses the correct name; only `internalApps` is wrong.) The manifest is owned by a k3s Addon controller, so `kubectl patch` on the ConfigMap reverts.

**Workaround:** Patch the manifest inside the devbox container (lost on container restart):

```bash
docker exec flyte-devbox sed -i \
  's|FLYTE_AWS_ENDPOINT: http://rustfs.flyte:9000|FLYTE_AWS_ENDPOINT: http://rustfs-svc.flyte:9000|' \
  /var/lib/rancher/k3s/server/manifests/flyte.yaml
docker exec flyte-devbox kubectl rollout restart deployment/flyte-binary -n flyte
```

**The restart races the addon controller — you usually need to restart twice.** Editing the manifest file triggers the k3s Addon controller to re-render the `flyte-binary-config` ConfigMap, but that's async. A `rollout restart` issued right after the `sed` will often boot a flyte-binary pod that mounts the *old* ConfigMap, and flyte-binary reads config only once at startup — so freshly-deployed App pods still get `FLYTE_AWS_ENDPOINT: http://rustfs.flyte:9000` even though the manifest file is patched. The deploy fails identically and looks like the patch didn't take.

Verify the live ConfigMap (not the manifest file) reflects the change, *then* restart again:

```bash
# confirm the ConfigMap the controller actually serves is patched
docker exec flyte-devbox kubectl get cm flyte-binary-config -n flyte -o yaml | grep -nE 'rustfs.*:9000'
# all hits should read rustfs-svc.flyte; then restart so flyte-binary loads it
docker exec flyte-devbox kubectl rollout restart deployment/flyte-binary -n flyte
docker exec flyte-devbox kubectl rollout status deployment/flyte-binary -n flyte --timeout=120s
```

To diagnose: check the actual env on a failed App pod — `kubectl get pod <pod> -n flyte -o yaml | grep -A1 FLYTE_AWS_ENDPOINT`. If it shows the bare `rustfs.flyte` while the ConfigMap shows `rustfs-svc.flyte`, flyte-binary is running stale config; restart it again. Delete the failed ksvc (`kubectl delete ksvc dashboard-flytesnacks-development -n flyte`) before redeploying so you get a clean revision.

---

## App pod needs `flyte.init_in_cluster()`, not `flyte.init()`

**Symptom:** `Client has not been initialized` from the first SDK call inside an App pod, even though FastAPI's lifespan called `flyte.init()`.

**Cause:** `fserve` spawns the configured `args` (e.g. uvicorn) as a `Popen(..., env=os.environ, shell=True)` subprocess. The subprocess inherits env vars but not Python process state, so the parent fserve's client init is lost. `flyte.init()` with no args does not auto-discover from env vars; `flyte.init_in_cluster()` does (reads `_U_EP_OVERRIDE`, `_U_INSECURE`, `EAGER_API_KEY`, `FLYTE_INTERNAL_EXECUTION_PROJECT/DOMAIN`, `_U_ORG_NAME`).

**Workaround:** In the App's own startup hook, branch on `_U_EP_OVERRIDE` and call `flyte.init_in_cluster(project=..., domain=...)`. Pass `project` explicitly — `with_servecontext(project=...)` does not propagate to the code-bundle upload client. See `app/init.py`.

---

## `flyte create project` (and any CLI subprocess) fails inside App pods

**Symptom:** Shelling out to `flyte create project ...` (or any `flyte` CLI command) from inside a running App pod raises `InitializationError` / `Client has not been initialized` immediately, even though the same pod's in-process Python SDK works fine.

**Cause:** Same root as the previous entry — the pod's Flyte connection is auto-discovered from `_U_EP_OVERRIDE` and friends at *Python process startup* by `flyte.init_in_cluster()`. A fresh subprocess inherits those env vars but does not run the discovery logic before its first SDK call, so `ensure_client()` raises. The Flyte v2 docs at `core-concepts/projects-and-domains` further claim that "the Python SDK provides read-only access to projects, to create or modify projects use the `flyte` CLI or the UI" — this is **wrong against the installed SDK**, `flyte.remote.Project.create(...)` exists and is what the CLI itself calls under the hood.

**Workaround:** When provisioning Flyte resources from inside an App pod, always prefer the in-process SDK (`Project.create.aio(...)`, `Project.get.aio(...)`, etc.) over CLI subprocesses. The pod's auto-discovered endpoint is only available to the parent Python process. Trust the SDK's actual surface over the v2 docs when they disagree. `app/onboard.py` creates projects this way, from the deployer's shell rather than a pod: on Union the in-cluster identity isn't allowed to create projects at all (a permission, not this quirk).

---

## Devbox dashboard: `cli/devbox_dashboard.py`

The app tier is built for Union, where onboarding gives each user a project and Union's login sits in front of every app. The devbox has neither, so it gets one dashboard from `uv run --all-extras python cli/devbox_dashboard.py` (after `cli/devbox-setup.sh`), which calls the same `app.onboard.deploy_dashboard` with devbox settings. Everything devbox-specific about it lives in that script and in this section; the code under `app/` stays target-agnostic. What it sets, and why:

- **Project and owner.** The default project (`flytesnacks`) and a stand-in owner, `devbox-user`, which is also the asset owner (`STARGAZER_OWNER`) and the folder in the store.
- **A stand-in user (`SG_STAND_IN_SUBJECT=devbox-user`).** Symptom without it: every dashboard page answers `401 not signed in` (`/health` and the index routes still work). The dashboard reads the user from `X-User-Subject`, which only Union's login sets. `app.identity` treats a request with no subject as the stand-in. `app.config.stand_in_subject` ignores the variable when `STARGAZER_TARGET=union`, and the script refuses to run off the devbox, so it can't reach Union. A real subject header still wins.
- **The store root, `s3://flyte-data/stargazer`.** `flyte-data` is the devbox's bucket, served by rustfs. Assets land under `stargazer/users/devbox-user/assets/<cid>/<name>` and the index replica under `stargazer/users/devbox-user/index`.
- **A storage port-forward while it deploys.** See "Storage signed URLs use `localhost`" above: the code bundle uploads to `rustfs-svc.flyte:9000`. The script holds `kubectl port-forward -n flyte svc/rustfs-svc 9000:9000` open, or reuses one already listening.

The dashboard ends up at `http://dashboard-flytesnacks-development.devbox.stargazer.bio:30081`. Its in-cluster address comes from the `INTERNAL_APP_ENDPOINT_PATTERN` the devbox gives app pods (`http://{app_fqdn}-flytesnacks-development.flyte.svc.cluster.local`), so pods index at `http://dashboard-flytesnacks-development.flyte.svc.cluster.local`.

**Runs submitted from the laptop** store into it when these are exported (`stargazer.config` forwards them into every pod), with the port-forward open for the code-bundle upload:

```bash
export STARGAZER_STORE_ROOT=s3://flyte-data/stargazer
export STARGAZER_INDEX_URL=http://dashboard-flytesnacks-development.flyte.svc.cluster.local
export STARGAZER_OWNER=devbox-user
kubectl port-forward -n flyte svc/rustfs-svc 9000:9000
```

The `verify-stargazer` skill's devbox recipe (`features/devbox-asset-storage.md`) checks all of this end to end.

---

## Litestream can't reach the devbox store without its endpoint and keys

**Symptom:** The devbox dashboard crash-loops before uvicorn starts. Its log shows `litestream restore` failing with `s3: cannot lookup bucket region: operation error S3: GetBucketLocation, get identity: get credentials: failed to refresh cached credentials, no EC2 IMDS role found` (measured 2026-10-08).

**Cause:** rustfs is S3-compatible but not AWS. Given a bare `s3://flyte-data/…` URL, Litestream talks to AWS, finds no region and no credentials, and the launcher stops the dashboard on the failed restore. Flyte gives app pods the store's address and keys as `FLYTE_AWS_ENDPOINT`, `FLYTE_AWS_ACCESS_KEY_ID` and `FLYTE_AWS_SECRET_ACCESS_KEY` (from `internalApps.defaultEnvVars`), names Litestream doesn't read.

**Fix (in code, target-agnostic):** `app.dashboard_launch` puts `FLYTE_AWS_ENDPOINT` on the replica URL as `?endpoint=` (Litestream then defaults to path-style addressing) and copies the `FLYTE_AWS_*` keys to `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` unless those are already set. On Union neither variable is set and the pod's role supplies credentials.

---

## Node has ~8 GiB allocatable memory

**Symptom:** OOM-killed pods when concurrent tasks exceed combined memory budget.

**Cause:** The single-node k3s cluster inside the devbox container has **~7.75 GiB allocatable**.

**Workaround:** Keep `outer-coordinator + concurrent children ≤ ~7.5 GiB`. The scRNA pipeline runs sequentially so a single child at `memory=("2Gi", "6Gi")` fits. Parallel fan-outs need smaller per-child limits.

---

## `App.url` is the console URL, not the public URL

**Symptom:** Browser redirected to `http://flyte-binary-http.flyte:8090/v2/...` after a successful `flyte.serve()`; "site can't be reached / DNS_PROBE" because the hostname is in-cluster only.

**Cause:** `flyte.remote.App.url` is documented as "the console URL for viewing the app" (i.e. the Flyte Console deep-link) — not the user-facing endpoint. The user-facing URL lives on `App.endpoint` (`status.ingress.public_url`). The SDK's own log line `"Deployed App ..., you can check the console at {deployed.url}"` is the giveaway. Not devbox-specific but easy to miss.

**Workaround:** Use `app.endpoint` whenever you mean "the URL a browser should hit." Reserve `app.url` for linking into the Flyte console.

---

## Serving domain must not be `.localhost` (so `App.endpoint` resolves in-cluster)

**Symptom:** A pod (e.g. the admin app) calling another App's `App.endpoint` over HTTP fails with `[Errno -2] Name or service not known` / `[Errno -5] No address associated with hostname`. Example: the since-removed notebook Save (`POST /workspace/save` → notebook pod's `/__sg__/workspace/sync`) returned `could not reach notebook: ...`. (The dashboard is Knative-scaled-to-zero between requests, so the failing call runs in a freshly-activated *pod*, not on the laptop — easy to misdiagnose as a local issue.)

**Cause:** Stock devbox serves apps under the `localhost` TLD, so `App.endpoint` is `http://{ksvc}.localhost:30081`. Two compounding problems: (1) cluster DNS doesn't know `*.localhost`; (2) more fundamentally, **glibc special-cases the `.localhost` TLD and never sends it to a nameserver at all** (`getaddrinfo('x.localhost')` → EAI_NODATA / EAI_NONAME without a single DNS query), so *no* CoreDNS change can fix `.localhost`. The fix is to move apps off `.localhost` onto a normal domain (here `devbox.stargazer.bio` — needs no real public DNS records) and make that domain resolve in-cluster. Then app code uses `App.endpoint` everywhere with **zero devbox branches**.

**Two hostnames must agree.** kourier routes by the request `Host`, so the Knative *route* host and Flyte's *`App.endpoint`* host must be the same domain or you get a 404 / no-route:
- **Knative `config-domain`** (`knative-serving` ns) sets the ksvc route host → `{ksvc}.{domain}`.
- **Flyte `internalApps.baseDomain`** (in `flyte-binary-config`'s `100-inline-config.yaml`) sets `App.endpoint` → `http://{ksvc}.{baseDomain}:{ingressAppsPort}`. `App.endpoint` is computed live from this — flyte-binary restart picks it up, **no app redeploy needed**. `ingressAppsPort: 30081` is the kourier NodePort (kept as-is so the laptop entrypoint is unchanged).

**Workaround (ad-hoc devbox steps, no app code).** Both domain values live in the k3s addon manifest, so patch the source (`kubectl edit` on the live ConfigMaps reverts):

```bash
# 1a. Knative route domain
docker exec flyte-devbox sed -i 's|^  localhost: ""|  devbox.stargazer.bio: ""|' \
  /var/lib/rancher/k3s/server/manifests/flyte.yaml
# 1b. Flyte App.endpoint domain
docker exec flyte-devbox sed -i 's|baseDomain: localhost|baseDomain: devbox.stargazer.bio|' \
  /var/lib/rancher/k3s/server/manifests/flyte.yaml
```

The addon controller re-applies within ~10s (it races — poll the live ConfigMaps before restarting):
`kubectl get cm config-domain -n knative-serving -o jsonpath='{.data}'` → `{"devbox.stargazer.bio":""}` and `kubectl get cm flyte-binary-config -n flyte -o yaml | grep baseDomain` → `devbox.stargazer.bio`. Then `kubectl rollout restart deployment/flyte-binary -n flyte` (Knative reconciles ksvc route URLs on its own).

2. Make `*.{domain}` resolve **to the node IP** inside the cluster (so the `:30081` NodePort is reachable from pods) via a `coredns-custom` server block. k3s CoreDNS imports `/etc/coredns/custom/*.server`. The node IP is hardcoded (re-apply on cluster recreate); fetch it at apply time:

```bash
NODEIP=$(docker exec flyte-devbox kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
docker exec -i flyte-devbox kubectl apply -f - <<YAML
apiVersion: v1
kind: ConfigMap
metadata: { name: coredns-custom, namespace: kube-system }
data:
  devbox-domain.server: |
    devbox.stargazer.bio:53 {
        template IN A {
            match .*\.devbox\.stargazer\.bio\.$
            answer "{{ .Name }} 60 IN A $NODEIP"
        }
        template IN AAAA {
            match .*\.devbox\.stargazer\.bio\.$
            rcode NOERROR
        }
    }
YAML

**CoreDNS template syntax is line-based — do not collapse to one line.** Each
`match`/`answer`/`rcode` directive must be on its own line inside the
`template … { }` block. The one-line `{ match … ; answer … }` form is invalid
Corefile syntax (`;` isn't a separator there) — CoreDNS rejects it with
`plugin/template: … Wrong argument count or unexpected line ending after 'template'`
and **CrashLoopBackOff**s, which takes cluster DNS down and cascades into
`flyte-binary` failing to start. (`cli/devbox-setup.sh` generates the
multi-line form.)
docker exec flyte-devbox kubectl rollout restart deployment/coredns -n kube-system
```

Why node IP and not the kourier ClusterIP: `App.endpoint` carries `:30081`, which is a NodePort — only reachable on a node IP, not on a ClusterIP (which listens on 80). kourier still routes by the public `Host`, so resolving to the node IP and hitting `:30081` works. The AAAA template returns NOERROR-empty so glibc (AF_UNSPEC) falls back to the A record cleanly.

**Verify** from a throwaway pod (`cli/devbox-setup.sh --verify-pod` does this with `python:3.13-slim` against the devbox dashboard):
`getaddrinfo('{ksvc}.devbox.stargazer.bio', 30081)` → node IP, and `GET http://{ksvc}.devbox.stargazer.bio:30081/health` → 200.

**Laptop side:** the browser already reached `*.localhost:30081` via 127.0.0.1 + the published `:30081` docker port; only the hostname changes. Point `*.devbox.stargazer.bio` → `127.0.0.1` with a wildcard resolver (the published `:30081` port is unchanged). No real public DNS records are needed — CoreDNS handles pods, the local resolver handles the laptop:

```bash
brew install dnsmasq
echo 'address=/devbox.stargazer.bio/127.0.0.1' >> $(brew --prefix)/etc/dnsmasq.conf
sudo brew services start dnsmasq
sudo mkdir -p /etc/resolver
printf 'nameserver 127.0.0.1\n' | sudo tee /etc/resolver/devbox.stargazer.bio
# verify: scutil --dns | grep -A1 devbox.stargazer.bio ; ping -c1 anything.devbox.stargazer.bio  -> 127.0.0.1
```

---

## `flyte.serve()` watch can report "failed" on a successful redeploy

**Symptom:** Redeploying an existing App (e.g. the dashboard, after changing `env_vars`) raises `RuntimeError: App deployment for app <name> has failed!` from `watch(wait_for="activated")` — but the app is actually fine. `app.onboard.deploy_dashboard` checks the app's real state before believing it.

**Cause:** The redeploy rolls a new Knative revision. While the rollout converges, the app's status can sample as failed and the SDK watch surfaces the first failed state it sees instead of waiting out the transition.

**Workaround:** Before re-running the deploy, check reality: `kubectl get ksvc -n flyte` (READY True, LATESTREADY = newest revision) and curl the endpoint. If the ksvc is ready, the deploy succeeded and the error is noise. Observed 2026-06-11 redeploying admin-app with a new `PINATA_JWT`: watch raised, yet both revisions were Running 2/2 and `/assets` served 200 seconds later. Distinct from the CrashLoopBackOff "has failed!" below, where the pod really is down.

---

## Auth cookies are non-`Secure` on devbox (http), `Secure` in prod (TLS)

> **Obsolete since plan 25:** the app tier sets no cookies any more (Union owns sign-in), and `STARGAZER_SECURE_COOKIES` is gone. Kept so a regression is recognizable if cookies come back.

**Symptom (if mis-defaulted):** With `Secure` cookies forced on, login over devbox's plain HTTP silently fails — the browser never sends a `Secure` cookie over http, so every request looks unauthenticated and you bounce back to the login page.

**Cause:** Devbox serves the admin and per-notebook apps over `http://…:30081` (no TLS). A `Secure` cookie is dropped by the browser on http, so it can never round-trip.

**Workaround / design:** The `Secure` attribute is **parametrized**, not hardcoded — `app.config.SECURE_COOKIES` (the app-tier config home) parses `STARGAZER_SECURE_COOKIES` (truthy = `1/true/yes/on`), defaulting **off** under `STARGAZER_TARGET=devbox` and **on** under `union`; an explicit value overrides either. The resolved value is baked as `1`/`0` into the admin App env (`_PUBLIC_CONFIG`, re-serialized from `config.SECURE_COOKIES`) and propagated into each notebook pod's env (`per_notebook_env`), so the standalone proxy's mirror (`sg_proxy._cookie_secure`) — which can't import `app.config` — sets the cookie identically. `httponly=True` and `samesite="lax"` stay constant — only `Secure` is environment-dependent. All cookie writes go through `admin_app._session_redirect` (session) / the proxy middleware (launch handoff); there is no other set-cookie site to keep in sync.

---

## Flyte's code bundle ships only `.py` files

Not strictly devbox-specific but bites on every devbox deploy.

**Symptom:** Non-Python assets (HTML templates, YAML configs) missing at runtime in the deployed pod even though `pyproject.toml` lists them as `package-data`. The Flyte bundle on `/home/flyte/` shadows the installed copy on `sys.path`, so `package-data` doesn't help.

**Workaround:** Add `include=("dir/",)` (relative to the file where the env is instantiated) to the `AppEnvironment` / `TaskEnvironment`. Prefer `Path(__file__).parent / "asset_dir"` over `importlib.resources.files("pkg")` for asset lookup.

Related Python-side gotcha: modules imported only inside function bodies are excluded from Flyte's static-analysis code bundle. Make them statically reachable (e.g. import in the package `__init__.py`) or add to `include`.

---

## Static assets cache for years (1981 mtime + no Cache-Control)

Not devbox-specific in mechanism, but the code bundle is what triggers it, so it bites every deploy that changes a file under `app/static/`.

**Symptom:** After redeploying the admin app with a changed static file (e.g. `cytoscape.min.js`), the browser keeps using the *old* file — surviving ordinary reloads — even though `curl .../static/<file>` returns the new one.

**Cause:** Flyte's code bundle unpacks every file with a fixed **1981** mtime, and stock Starlette `StaticFiles` sends `Last-Modified: 1981` with **no `Cache-Control`**. Browsers then apply *heuristic* freshness — roughly 10% of (now − Last-Modified), about 4.5 years from a 1981 date — so the asset is considered fresh for years and never revalidated.

**Workaround (in code):** `app/admin_app.py` mounts `_RevalidatingStatic`, a `StaticFiles` subclass that stamps `Cache-Control: no-cache` on every file response ("store but always revalidate"). The response already carries an ETag, so it is a cheap 304 when unchanged and a fresh 200 when changed.

A browser that cached a file *before* this fix still holds it under the old heuristic and will not ask again — one hard reload (or cache clear) moves it onto the revalidating path. If that ever proves insufficient (many stuck clients), the next layer is a content-hash `?v=` query on static URLs so a changed file gets a URL the browser has never cached; it was prototyped on the abandoned `asset-manager-frontend` branch (commit `5a4e5b6`, not merged).

---

## Flyte's code bundle shadows image-baked top-level packages

Not strictly devbox-specific. Bites any AppEnvironment whose image bakes a Python module under a package name that the deployer's process also imports from.

**Symptom:** `uvicorn <pkg>.<mod>:asgi_app` fails inside the pod with `ERROR: Error loading ASGI app. Could not import module "<pkg>.<mod>"`, even though `<pkg>/<mod>.py` is verifiably present at the image-baked path (e.g. `/usr/local/lib/app/proxy.py`) and `PYTHONPATH` includes that directory.

**Cause:** Flyte's `loaded_modules` bundler ships every `.py` file imported by the deploying Python process into the pod's WORKDIR (`/home/flyte`). If that bundle includes a `<pkg>/__init__.py` (because the deployer imports `<pkg>.something_else`), the unpacked `/home/flyte/<pkg>/` shadows the image-baked `/usr/local/lib/<pkg>/` on `sys.path` — Python's cwd entry (`''`) comes before `PYTHONPATH`. The cwd version doesn't contain the baked module that wasn't separately imported by the deployer, so the import fails.

**Workaround:** Bake the runtime-only file as a TOP-LEVEL module under a name the deployer doesn't import. E.g. `/usr/local/lib/sg_proxy.py` (not `/usr/local/lib/app/proxy.py`); reference it as `uvicorn sg_proxy:asgi_app`. The top-level slot is free; only package directories collide.

---

## Laptop-side Flyte cache goes stale when the devbox is recreated/restarted

**Symptom (two faces, same cause).** After recreating or restarting the devbox, a deploy (`cli/devbox_dashboard.py`) fails in one of two places:

1. **Image stage** — `flyte.build` logs `Image localhost:30000/notebook-app:<hash> already exists, skipping build`, then the retag dies:

   ```
   ERROR: localhost:30000/notebook-app:<hash>: not found
   CalledProcessError: docker buildx imagetools create -t .../notebook-app:latest .../notebook-app:<hash>
   ```

2. **Serve stage** — images are fine, `flyte.serve` logs `Code bundle found in cache, skipping upload`, then `RuntimeError: App deployment for app admin-app has failed!` and the App pod CrashLoopBackOffs with:

   ```
   FileNotFoundError: Object at location uploads/flytesnacks/development/.../fast<hash>.tar.gz not found
   … Server returned non-2xx status code: 404 Not Found (HEAD http://rustfs-svc.flyte:9000/flyte-data/…)
   ```

**Cause:** the devbox wipes **all** of its persistent state on recreate — the in-container docker registry *and* rustfs object storage. The Flyte SDK's cache lives on the **laptop** and survives. `PersistentCacheImageChecker` is first in the image-existence checker chain and returns a cached URI **without ever contacting the registry** (`flyte/_internal/imagebuild/image_builder.py`); `bundle_cache` does the same for code-bundle uploads. So the SDK skips work whose artifacts no longer exist, and the failure surfaces later as a missing manifest or a 404 on bundle download.

Entries have a **1-day TTL** (`_IMAGE_CACHE_TTL_DAYS`), so this is intermittent: it bites when you recreate the devbox within a day of a successful deploy, and self-heals after that.

**Clearing `image_cache` alone is not enough** — the same wipe invalidates `bundle_cache`, which just moves the failure from the image stage to the serve stage.

**Where the cache actually lives.** `LocalDB._get_cache_dir()` uses the **config file's parent** when a config is found, so with this repo's `.flyte/config.yaml` the DB is at `<project>/.flyte/local-cache/cache.db` — **not** `~/.flyte/local-cache`, which is what `flyte delete local-cache` documents. Check which one exists before trusting that command to have done anything.

**Workaround:** after any devbox recreate/restart, clear the cache before deploying:

```bash
python - <<'PY'
import sqlite3
c = sqlite3.connect(".flyte/local-cache/cache.db")
for t in ("image_cache", "bundle_cache", "task_cache", "runs"):
    c.execute(f"DELETE FROM {t}")
c.commit()
PY
```

`task_cache` and `runs` point at the same wiped object storage, so clear them too. Then delete any failed ksvc (`kubectl delete ksvc dashboard-flytesnacks-development -n flyte`) so the redeploy gets a clean revision.

## `AppEnvironment.clone_with` breaks `include=` (and the pod loader)

Not devbox-specific: any Flyte target, SDK 2.10.7.

**Symptom:** Serving a `clone_with` copy of an AppEnvironment that has `include=("templates/", ...)` fails before deploy with `ValueError: include path '…/lib/python3.13/templates' is not a file, directory, or matching glob pattern.` — the path is inside the Python install, not the project.

**Cause:** An AppEnvironment records the frame it was created in (`_caller_frame`), skipping SDK and synthesized frames. Flyte resolves `include=` paths relative to that frame's file, and `AppEnvResolver` uses it to find the module the pod imports the env from. `clone_with` builds the copy with `dataclasses.replace`, so the copy's frame is the standard library's `dataclasses.py`. Seen 2026-10-06 on the first real `stargazer-users onboard`.

**Workaround:** Don't serve a `clone_with` copy of an env that uses `include=`. `app/onboard.py` sets the per-user `env_vars` and `domain` on `app_env` itself before each serve (it's a plain, non-frozen dataclass), keeping the original frame. `tests/unit/test_onboard.py::test_dashboard_deploy_keeps_the_env_resolvable` pins this.
