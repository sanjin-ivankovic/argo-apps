# Operations

Day-2 runbook for the platform: how to sync, validate, inspect, and rotate
the things you touch routinely. For symptom-based debugging (sync stuck,
ingress 404, login loop, cert not issuing), see
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Table of Contents

- [Sync Model](#sync-model)
- [Deploying a Change](#deploying-a-change)
- [Inspecting State](#inspecting-state)
- [Validating Before Commit](#validating-before-commit)
- [Secret Rotation](#secret-rotation)
- [Routine Checks](#routine-checks)
  - [Alerts](#alerts)

## Sync Model

User-tier apps (`apps/user/*`) carry `autoSync: true` in their
`config.yaml`: a push to `main` syncs them, with prune and selfHeal. Infra,
data and services apps never auto-sync: after pushing to `main` you must
**manually sync** them in the ArgoCD UI at <https://argo.example.com>, or
via the CLI.

The full chain: a push to `main` is what ArgoCD reconciles against, but it
will not apply changes until you sync. The ApplicationSet itself
(`argocd/apps-set.yaml`) also needs a sync to pick up newly added
`apps/*/*/config.yaml` files before the per-app Application appears.

## Deploying a Change

```bash
# 1. Validate locally (see Validating Before Commit)
python3 .ci/scripts/validate_app.py apps/<tier>/<app>

# 2. Commit and push to main
git add apps/<tier>/<app>/
git commit -m "feat(<app>): <change>"
git push

# 3. Sync the ApplicationSet first if you added a NEW app
argocd app sync apps

# 4. Sync the app
argocd app sync <app>
argocd app wait <app>
```

A new app appears only after the ApplicationSet is synced (it discovers the
new `config.yaml`), then the generated Application can be synced.

## Inspecting State

```bash
# All generated Applications and their sync/health status
kubectl get applications -n argocd

# The ApplicationSet that generates them
kubectl get applicationsets -n argocd

# Detail for one app (sync status, last error, revision)
argocd app get <app>
kubectl describe application <app> -n argocd
```

## Validating Before Commit

```bash
# Which apps changed (used by CI fan-out)
python3 .ci/scripts/detect_apps.py

# Full validate for one app: kustomize build -> kubeconform
python3 .ci/scripts/validate_app.py apps/<tier>/<app>

# Render only, no schema validation
kubectl kustomize apps/<tier>/<app>

# ApplicationSet / bootstrap changes
kubectl kustomize argocd

# Lint and secret-scan changed files
pre-commit run --files <changed-files>
```

The sanitize tooling lives in `homelab/ci-components` (baked into ci-base at
`/opt/ci/`), not in this repo. To prove a change is mirror-safe before the
nightly run, dry-run the publish from a ci-components checkout:
`python3 .ci/scripts/publish_github.py --source <argo-apps> --output /tmp/out
--github-repo argo-apps --dry-run` runs sanitize, verify and gitleaks without
pushing.

## Secret Rotation

Secrets are defined in `kryptos/configs/<app>.yaml` and sealed into
`apps/<tier>/<app>/secrets/`. The kryptos engine is a separate repo; run a
released binary from the repo root. See [SECURITY.md](SECURITY.md) and
[../kryptos/README.md](../kryptos/README.md).

```bash
# Validate every config (no cluster needed)
kryptos validate

# Detect config <-> sealed-secret drift
kryptos audit

# Regenerate and reseal one secret
kryptos rotate --app <app> --secret <secret>
```

After resealing, commit the updated SealedSecret and sync the app. The
sealed-secrets controller in `kube-system` unseals it into a Kubernetes
`Secret`.

## Routine Checks

```bash
# Edge: pods, routes, certificates
kubectl get pods -n traefik
kubectl get ingressroute -A
kubectl get certificates -A

# Data: stateful pods and volumes
kubectl get pods -n postgresql
kubectl get pods -n valkey
kubectl get pvc -A
```

### Alerts

Alertmanager (`apps/infra/kube-prometheus-stack/`) sends every firing and
resolved alert to the ntfy topic `alerts` through the `ntfy-alertmanager`
bridge in the same namespace. `Watchdog` and `InfoInhibitor` go to the
`null` receiver. When alerts stop arriving, check the chain in order:

```bash
kubectl -n monitoring get pods
kubectl -n monitoring logs deploy/ntfy-alertmanager
kubectl -n ntfy logs deploy/ntfy | grep -i alertmanager
```

Log shipping: `LogShipperDown` (Alloy on an LXC stopped),
`LogShipperPushFailing` (Loki keeps answering 5xx, so that shipper's queue
is stalled) and `LogShipperDroppingEntries`. Storage and TLS:
`LonghornVolumeDegraded` / `LonghornVolumeFaulted`, `CertificateExpiringSoon`
(cert-manager renewal failing for two weeks) and `CertificateNotReady`.

Host alerts (`HostExporterDown`, `HostRootDisk*`, `HostMemoryLow`,
`HostSystemdUnitFailed`, `HostContainerRestarting`) cover the Proxmox LXCs.
`EtcdBackupStale` means the nightly Semaphore task "Talos: etcd Backup"
failed or did not run; `EtcdBackupMetricMissing` means node_exporter or the
`etcd-backup-age` timer on semaphore stopped.

Firing alerts and silences: <https://alertmanager.example.com> (LAN only).
Scrape targets: <https://prometheus.example.com/targets>. etcd is scraped on
2383 with the `etcd-client-cert` client certificate (CN=prometheus, issued
from the Talos etcd CA, valid until 2036-11-01).
