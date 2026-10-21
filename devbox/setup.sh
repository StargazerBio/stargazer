#!/usr/bin/env bash
#
# setup.sh — make a fresh `flyte-devbox` container ready for Stargazer.
# Tasks and workflows run on the devbox, and devbox/dashboard.py deploys a
# dashboard there for a stand-in user (the devbox has no Union login).
#
# The devbox is the local Flyte v2 cluster (k3s, flyte-binary, rustfs, Knative
# and a registry in one Docker container). Most of it behaves like a hosted
# Flyte deploy; each step below works around one way it doesn't. The changes
# live in the k3s addon manifest, CoreDNS and the cluster, so they're lost
# whenever the container is recreated: re-run this after every fresh devbox.
# Re-running an already set-up box changes nothing, apart from the restarts.
#
# Steps:
#   1. Storage signed URLs: localhost:30002 → rustfs-svc.flyte:9000
#   2. Serving domain: `.localhost` → devbox.stargazer.bio (Knative and Flyte)
#   3. CoreDNS wildcard: *.devbox.stargazer.bio → the node's IP
#   4. The PINATA_JWT task secret
#   5. The asset index's Postgres server (devbox/postgres.yaml)
#   6. Clearing Flyte's local cache in every checkout
#   7. Checks, and DNS on this machine (printed; applied with --laptop)
#
# What it can't fix:
#   - The devbox drops `secrets=` on an AppEnvironment. flyte-binary never
#     stamps the secret annotations on app pods, so the secret webhook has
#     nothing to act on (Union does inject app secrets). Dashboards and
#     notebook pods go without PINATA_JWT here, so the devbox has no public
#     tier in the asset browser or in notebooks. Baking the key into
#     `env_vars` would show it to every user in their app's spec.
#   - Memory. The node has ~7.75 GiB allocatable, and the cluster's own pods,
#     the dashboard and the index's Postgres request ~1.7 GiB of it (1,710 Mi
#     measured 2026-10-20). Scheduling counts requests, and a parent task holds
#     its request while it waits on its children, so a workflow's pods must fit
#     together in ~6 GiB. That's why gatk_env requests 1 GiB
#     (src/stargazer/config.py).
#   - Stopping an app only scales it to zero. flyte-binary keeps the app's
#     Knative service when it's deactivated (Union removes it), so the next
#     request starts a pod again: a stopped notebook's open tab polls every
#     10 s and brings it back, and the new pod hydrates and saves the
#     workspace as usual (measured 2026-10-21). Close a stopped notebook's
#     tab; deleting the notebook removes its service.
#   - Notebook pods run as root. The local image builder leaves the notebook
#     image at `USER root` where Union's builder ends at `flyte`, so pods
#     start as root with HOME=/root. Edit mode, saving and the terminal (with
#     Claude Code) all work that way (measured 2026-10-21).
#   - Architecture. On Apple silicon the node is arm64 (an x86_64 devbox
#     can't start pods: seccomp is unsupported under emulation). Stargazer's
#     images are x86_64 only, because GATK's GenomicsDB native library is, so
#     its pods run emulated (IMAGE_PLATFORM in src/stargazer/config.py).
#
# --verify-pod resolves and calls the devbox dashboard from a throwaway pod,
# so deploy it first.
#
# Usage:
#   devbox/setup.sh [--dry-run] [--laptop] [--verify-pod]
#
set -euo pipefail

CONTAINER="${DEVBOX_CONTAINER:-flyte-devbox}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
DOMAIN="devbox.stargazer.bio"
MANIFEST="/var/lib/rancher/k3s/server/manifests/flyte.yaml"
DRY_RUN=0
DO_LAPTOP=0
VERIFY_POD=0

c_blue=$'\033[1;34m'; c_green=$'\033[1;32m'; c_yellow=$'\033[1;33m'; c_red=$'\033[1;31m'; c_off=$'\033[0m'
log()  { printf '%s▸ %s%s\n' "$c_blue"  "$*" "$c_off"; }
ok()   { printf '%s✓ %s%s\n' "$c_green" "$*" "$c_off"; }
warn() { printf '%s! %s%s\n' "$c_yellow" "$*" "$c_off" >&2; }
die()  { printf '%s✗ %s%s\n' "$c_red"  "$*" "$c_off" >&2; exit 1; }

# Print the leading comment block (stops at the first non-comment line, so it
# survives edits to the header without a hardcoded line count).
usage() { sed -n '2,${/^#/!q;p;}' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)    DRY_RUN=1 ;;
        --laptop)     DO_LAPTOP=1 ;;
        --verify-pod) VERIFY_POD=1 ;;
        -h|--help)    usage ;;
        *) die "unknown argument: $1 (try --help)" ;;
    esac
    shift
done

dex()  { docker exec "$CONTAINER" "$@"; }
flyte_cli() { uv run --project "$REPO" flyte --config "$REPO/.flyte/config.yaml" "$@"; }
kc()   { docker exec "$CONTAINER" kubectl "$@"; }
# Run a mutating command, or just print it under --dry-run.
run()  { if [ "$DRY_RUN" = 1 ]; then printf '   %s[dry-run]%s %s\n' "$c_yellow" "$c_off" "$*"; else "$@"; fi; }

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker not found on PATH"
docker ps --format '{{.Names}}' | grep -qx "$CONTAINER" \
    || die "devbox container '$CONTAINER' is not running (set DEVBOX_CONTAINER to override)"
dex test -f "$MANIFEST" || die "addon manifest not found at $MANIFEST inside $CONTAINER"
log "Target container=$CONTAINER  dry-run=$DRY_RUN"

# ---------------------------------------------------------------------------
# 1–2. Patch the k3s addon manifest. The ConfigMaps are owned by k3s's addon
#      controller, so editing them directly reverts: patch the source manifest
#      and let the controller re-render them.
#
#   1. flyte-binary hands out signed upload URLs on its configured
#      `signedURL.endpoint`, localhost:30002. In a pod `localhost` is the pod
#      itself, so every code-bundle upload from a pod (`flyte.serve` in the
#      dashboard) fails with "All connection attempts failed". The in-cluster
#      service name works from pods, as real S3 URLs do in production. This
#      machine then needs that name too (step 7).
#   2. Apps are served under `.localhost`, and glibc answers `*.localhost`
#      without asking any nameserver, so no DNS change makes `App.endpoint`
#      resolve in a pod. A normal domain fixes it with no devbox branch in the
#      app code. It needs no public DNS records. kourier routes by Host, so
#      Knative's route domain (`config-domain`) and Flyte's
#      `internalApps.baseDomain`, which builds `App.endpoint`, must match.
# ---------------------------------------------------------------------------
log "Patching addon manifest ($MANIFEST)"
run dex sed -i \
    -e 's|endpoint: http://localhost:30002|endpoint: http://rustfs-svc.flyte:9000|g' \
    -e 's|^  localhost: ""|  '"$DOMAIN"': ""|' \
    -e "s|baseDomain: localhost|baseDomain: $DOMAIN|" \
    "$MANIFEST"
ok "Manifest patched (signed-URL endpoint, Knative domain, baseDomain)"

# Wait for the addon controller to re-render the live ConfigMaps (about 10 s).
# flyte-binary reads its config once at startup, so a restart before the
# ConfigMap changes boots the old config, and the deploy then fails as if
# nothing had been patched.
log "Waiting for the k3s addon controller to re-render ConfigMaps"
if [ "$DRY_RUN" = 1 ]; then
    printf '   %s[dry-run]%s poll flyte-binary-config / config-domain until patched\n' "$c_yellow" "$c_off"
else
    rendered=0
    for _ in $(seq 1 30); do
        cm="$(kc get cm flyte-binary-config -n flyte -o yaml 2>/dev/null || true)"
        dom="$(kc get cm config-domain -n knative-serving -o jsonpath='{.data}' 2>/dev/null || true)"
        if grep -q "baseDomain: $DOMAIN" <<<"$cm" \
            && grep -q "$DOMAIN" <<<"$dom"; then
            rendered=1; break
        fi
        sleep 2
    done
    [ "$rendered" = 1 ] && ok "Live ConfigMaps reflect the patch" \
        || warn "ConfigMaps not fully patched after 60s — inspect manually before relying on a deploy"
fi

# `App.endpoint` is computed live from baseDomain, so the restart is enough:
# deployed apps don't need redeploying, and Knative updates its routes itself.
log "Restarting flyte-binary"
run kc rollout restart deployment/flyte-binary -n flyte
# Non-fatal: a slow rollout shouldn't abort the script before later steps run.
# (flyte-binary needs healthy cluster DNS to start, so a stall here usually
# means coredns is unhealthy — the verify section reports the true state.)
run kc rollout status deployment/flyte-binary -n flyte --timeout=180s \
    || warn "flyte-binary rollout slow/incomplete — continuing; check 'kubectl get pods -n flyte'"
ok "flyte-binary restart issued"

# ---------------------------------------------------------------------------
# 3. CoreDNS wildcard, so pods resolve the domain from step 2
#    (devbox/coredns-custom.yaml, with this node's IP filled in).
# ---------------------------------------------------------------------------
log "Applying coredns-custom for *.$DOMAIN"
if [ "$DRY_RUN" = 1 ]; then
    printf '   %s[dry-run]%s kubectl apply devbox/coredns-custom.yaml (node IP fetched at apply time)\n' "$c_yellow" "$c_off"
else
    NODEIP="$(kc get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')"
    [ -n "$NODEIP" ] || die "could not determine node InternalIP"
    sed "s/NODE_IP/$NODEIP/" "$HERE/coredns-custom.yaml" \
        | docker exec -i "$CONTAINER" kubectl apply -f -
    ok "coredns-custom applied (*.$DOMAIN → $NODEIP)"
fi
log "Restarting coredns"
run kc rollout restart deployment/coredns -n kube-system
run kc rollout status deployment/coredns -n kube-system --timeout=120s \
    || warn "coredns rollout slow/incomplete — a CrashLoop here means the custom config is invalid; check 'kubectl logs -n kube-system -l k8s-app=kube-dns'"
ok "coredns restart issued"

# ---------------------------------------------------------------------------
# 4. The PINATA_JWT secret. Every task environment declares it
#    (STARGAZER_SECRETS), and the pod webhook refuses a pod whose declared
#    secret doesn't exist ("none of the secret managers injected secret"), so
#    without it no task runs. Flyte has no optional secrets. Union has it
#    org-wide; it's created org-wide here too. Its value comes from
#    $PINATA_JWT, else the repo's .env; with neither it's empty, and task pods
#    run without the public tier. Replaced on every run, so a changed key takes
#    effect.
# ---------------------------------------------------------------------------
log "Creating the PINATA_JWT task secret"
jwt="${PINATA_JWT:-}"
if [ -z "$jwt" ] && [ -f "$REPO/.env" ]; then
    jwt="$(sed -n "s/^PINATA_JWT=//p" "$REPO/.env" | tail -1 | tr -d "\"'")"
fi
[ -n "$jwt" ] || warn "no PINATA_JWT in the environment or .env — the secret is empty, so task pods run without the public tier"
if [ "$DRY_RUN" = 1 ]; then
    printf '   %s[dry-run]%s flyte delete secret PINATA_JWT; flyte create secret PINATA_JWT --from-file <value>\n' "$c_yellow" "$c_off"
else
    secret_file="$(mktemp)"
    trap 'rm -f "$secret_file"' EXIT
    printf '%s' "$jwt" > "$secret_file"
    flyte_cli delete secret PINATA_JWT >/dev/null 2>&1 || true  # absent on a fresh devbox
    flyte_cli create secret PINATA_JWT --from-file "$secret_file" >/dev/null \
        || die "could not create the PINATA_JWT secret (is flyte-binary up? 'kubectl get pods -n flyte')"
    rm -f "$secret_file"
    ok "PINATA_JWT secret created"
fi

# ---------------------------------------------------------------------------
# 5. The asset index's Postgres server. On Union each user's index is a SQLite
#    file on their dashboard; here one Postgres server serves the dashboard and
#    every pod. Applied on every run; an unchanged spec is a no-op.
# ---------------------------------------------------------------------------
log "Applying the asset index's Postgres server (devbox/postgres.yaml)"
if [ "$DRY_RUN" = 1 ]; then
    printf '   %s[dry-run]%s kubectl apply devbox/postgres.yaml\n' "$c_yellow" "$c_off"
else
    docker exec -i "$CONTAINER" kubectl apply -f - < "$HERE/postgres.yaml"
    kc rollout status deployment/postgres -n stargazer --timeout=180s \
        || warn "Postgres rollout slow/incomplete — check 'kubectl get pods -n stargazer'"
    ok "Postgres applied (postgres.stargazer.svc.cluster.local:5432)"
fi

# ---------------------------------------------------------------------------
# 6. Clear Flyte's local cache. Recreating the devbox wipes its registry and
#    object store, but the SDK's cache on this machine survives (entries last
#    a day) and skips work whose artifacts are gone. With a cached image the
#    build is skipped and the retag fails ("…notebook-app:<hash>: not found").
#    With a cached code bundle the upload is skipped and the app pod
#    crash-loops on a 404 for its bundle. The cache sits beside the config
#    file in use, so every checkout of this repo (each worktree) has its own
#    .flyte/local-cache, and none is the ~/.flyte/local-cache that
#    `flyte delete local-cache` clears. This clears them all.
# ---------------------------------------------------------------------------
log "Clearing Flyte's local cache in every checkout"
git -C "$REPO" worktree list --porcelain | sed -n 's/^worktree //p' | while read -r checkout; do
    cache="$checkout/.flyte/local-cache/cache.db"
    [ -f "$cache" ] || continue
    run uv run --project "$REPO" python -c "
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
for table in ('image_cache', 'bundle_cache', 'task_cache', 'runs'):
    try:
        db.execute(f'DELETE FROM {table}')
    except sqlite3.OperationalError:
        pass
db.commit()
" "$cache"
    ok "Cleared $cache"
done

# ---------------------------------------------------------------------------
# Verify (read-only)
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = 0 ]; then
    log "Verifying cluster-side state"
    cm="$(kc get cm flyte-binary-config -n flyte -o yaml 2>/dev/null || true)"
    grep -q "baseDomain: $DOMAIN" <<<"$cm" && ok "baseDomain=$DOMAIN" || warn "baseDomain not set to $DOMAIN"
    kc get cm coredns-custom -n kube-system -o name >/dev/null 2>&1 \
        && ok "coredns-custom present" || warn "coredns-custom missing"
    flyte_cli get secret 2>/dev/null | grep -q PINATA_JWT \
        && ok "PINATA_JWT secret present" || warn "PINATA_JWT secret missing — task pods will be rejected"
    [ "$(kc get deployment postgres -n stargazer -o jsonpath='{.status.readyReplicas}' 2>/dev/null)" = 1 ] \
        && ok "Postgres ready" || warn "Postgres not ready — runs can't index their assets"

    if [ "$VERIFY_POD" = 1 ]; then
        log "Throwaway-pod DNS/HTTP check (may take ~30s)"
        host="dashboard-flytesnacks-development.$DOMAIN"
        kc run sg-devbox-check --rm -i --restart=Never \
            --image=python:3.13-slim --command -- \
            python -c "import socket, urllib.request; print('resolves:', socket.getaddrinfo('$host', 30081)[0][4]); print('health:', urllib.request.urlopen('http://$host:30081/health', timeout=60).status)" \
            2>/dev/null || warn "pod check failed (is the dashboard deployed? devbox/dashboard.py — non-fatal)"
    fi
fi

# ---------------------------------------------------------------------------
# 7. DNS on this machine (macOS, sudo), once per machine. Printed by default;
#    applied with --laptop.
#
#    - rustfs-svc.flyte → 127.0.0.1, plus a port-forward to it on :9000, so
#      code-bundle uploads from here reach the store at the signed-URL host
#      from step 1. devbox/dashboard.py and the devbox tests hold the forward
#      open themselves; a `flyte.run` submitted by hand needs it running, or
#      the upload fails with "ConnectError: All connection attempts failed".
#    - *.devbox.stargazer.bio → 127.0.0.1, so the browser reaches apps on the
#      published :30081 port.
# ---------------------------------------------------------------------------
laptop_steps() {
    cat <<EOF
  # 1) Resolve the storage host to a port-forward on :9000 (devbox/dashboard.py opens one while it deploys; run 'kubectl port-forward -n flyte svc/rustfs-svc 9000:9000' when submitting runs yourself):
  echo '127.0.0.1 rustfs-svc.flyte' | sudo tee -a /etc/hosts

  # 2) Wildcard-resolve *.$DOMAIN → 127.0.0.1 (the published :30081 port is unchanged):
  brew install dnsmasq
  echo 'address=/$DOMAIN/127.0.0.1' >> "\$(brew --prefix)/etc/dnsmasq.conf"
  sudo brew services restart dnsmasq
  sudo mkdir -p /etc/resolver
  printf 'nameserver 127.0.0.1\n' | sudo tee /etc/resolver/$DOMAIN
  # verify: scutil --dns | grep -A1 $DOMAIN ; ping -c1 anything.$DOMAIN  # → 127.0.0.1
EOF
}

if [ "$DO_LAPTOP" = 1 ]; then
    log "Applying DNS on this machine (needs sudo + Homebrew)"
    command -v brew >/dev/null 2>&1 || die "Homebrew required for --laptop"
    grep -q 'rustfs-svc.flyte' /etc/hosts 2>/dev/null \
        || run bash -c "echo '127.0.0.1 rustfs-svc.flyte' | sudo tee -a /etc/hosts >/dev/null"
    brew list dnsmasq >/dev/null 2>&1 || run brew install dnsmasq
    conf="$(brew --prefix)/etc/dnsmasq.conf"
    grep -q "address=/$DOMAIN/127.0.0.1" "$conf" 2>/dev/null \
        || run bash -c "echo 'address=/$DOMAIN/127.0.0.1' >> '$conf'"
    run sudo brew services restart dnsmasq
    run sudo mkdir -p /etc/resolver
    run bash -c "printf 'nameserver 127.0.0.1\n' | sudo tee /etc/resolver/$DOMAIN >/dev/null"
    ok "DNS on this machine applied"
else
    log "DNS on this machine (run once; re-run with --laptop to apply):"
    laptop_steps
fi

ok "Devbox set up."
