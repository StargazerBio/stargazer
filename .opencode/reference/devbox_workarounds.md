# Devbox Workarounds

`cr.flyte.org/flyteorg/flyte-devbox` is the local Flyte v2 dev cluster (k3s + flyte-binary + rustfs + knative + docker-registry inside one Docker container). Most behavior matches a production Flyte deploy, but several quirks bite us on every deploy iteration. This file is the running ledger of those quirks and how to step around them.

When you hit a deploy/runtime issue against devbox that takes more than one round-trip to diagnose, append it here with a one-line description and the minimum the next session needs to know.

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

   `app/admin_app.py:main()` starts the port-forward automatically (`_start_storage_port_forward()`) so `python -m app.admin_app` "just works" given the DNS step is done once.

---

## `AppEnvironment(secrets=[...])` is silently dropped

**Symptom:** Secret registered with `flyte create secret`, declared on the `AppEnvironment` via `secrets=[flyte.Secret(...)]`, never reaches the running container. `os.environ["MY_SECRET"]` raises `KeyError`.

**Cause:** The injection webhook (`flyte-binary-webhook`) requires the pod label `inject-flyte-secrets: "true"`. Task pods get this label automatically; **App pods (Knative-managed) do not**, so the webhook skips them.

**Workaround:** Bake secret values into `env_vars={...}` from the deployer's local shell at deploy time. Example in `app/admin_app.py`:

```python
_SECRET_NAMES = ("GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "SESSION_SECRET")
_RUNTIME_SECRETS = {
    name: os.environ[name] for name in _SECRET_NAMES if os.environ.get(name)
}
app_env = flyte.app.AppEnvironment(..., env_vars=_RUNTIME_SECRETS)
```

Deployer must `export GITHUB_CLIENT_ID=…` etc. before `python -m app.admin_app`. Trade-off: secret values live in the App spec stored by Flyte. Acceptable on devbox; revisit for prod.

Alternative (verbose): attach a `pod_template=PodTemplate(labels={"inject-flyte-secrets": "true"}, ...)` with a full V1PodSpec whose primary container is named `"app"`.

---

## `flyte.serve()` fails with `rustfs.flyte` DNS error

**Symptom:** App pod crash-loops before user code runs, logs show `GenericError: Generic S3 error ... http://rustfs.flyte:9000/... Name or service not known`.

**Cause:** `/var/lib/rancher/k3s/server/manifests/flyte.yaml` (line ~7776) sets `internalApps.defaultEnvVars.FLYTE_AWS_ENDPOINT = http://rustfs.flyte:9000`. The actual k8s service is `rustfs-svc`. (The `plugins.k8s.default-env-vars` block uses the correct name; only `internalApps` is wrong.) The manifest is owned by a k3s Addon controller, so `kubectl patch` on the ConfigMap reverts.

**Workaround:** Patch the manifest inside the devbox container (lost on container restart):

```bash
docker exec flyte-devbox sed -i \
  's|FLYTE_AWS_ENDPOINT: http://rustfs.flyte:9000|FLYTE_AWS_ENDPOINT: http://rustfs-svc.flyte:9000|' \
  /var/lib/rancher/k3s/server/manifests/flyte.yaml
docker exec flyte-devbox kubectl rollout restart deployment/flyte-binary -n flyte
```

---

## App pod needs `flyte.init_in_cluster()`, not `flyte.init()`

**Symptom:** `Client has not been initialized` from the first SDK call inside an App pod, even though FastAPI's lifespan called `flyte.init()`.

**Cause:** `fserve` spawns the configured `args` (e.g. uvicorn) as a `Popen(..., env=os.environ, shell=True)` subprocess. The subprocess inherits env vars but not Python process state, so the parent fserve's client init is lost. `flyte.init()` with no args does not auto-discover from env vars; `flyte.init_in_cluster()` does (reads `_U_EP_OVERRIDE`, `_U_INSECURE`, `EAGER_API_KEY`, `FLYTE_INTERNAL_EXECUTION_PROJECT/DOMAIN`, `_U_ORG_NAME`).

**Workaround:** In the App's own startup hook, branch on `_U_EP_OVERRIDE` and call `flyte.init_in_cluster(project=..., domain=...)`. Pass `project` explicitly — `with_servecontext(project=...)` does not propagate to the code-bundle upload client. See `app/init.py`.

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

## Flyte's code bundle ships only `.py` files

Not strictly devbox-specific but bites on every devbox deploy.

**Symptom:** Non-Python assets (HTML templates, YAML configs) missing at runtime in the deployed pod even though `pyproject.toml` lists them as `package-data`. The Flyte bundle on `/home/flyte/` shadows the installed copy on `sys.path`, so `package-data` doesn't help.

**Workaround:** Add `include=("dir/",)` (relative to the file where the env is instantiated) to the `AppEnvironment` / `TaskEnvironment`. Prefer `Path(__file__).parent / "asset_dir"` over `importlib.resources.files("pkg")` for asset lookup.

Related Python-side gotcha: modules imported only inside function bodies are excluded from Flyte's static-analysis code bundle. Make them statically reachable (e.g. import in the package `__init__.py`) or add to `include`.
