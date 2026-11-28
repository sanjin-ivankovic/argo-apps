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
- [Workload Balance](#workload-balance)

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

Secret values live in HashiCorp Vault, `kv/k8s/<namespace>/<secret>`; each
app's `ExternalSecret` in `apps/<tier>/<app>/secrets/` names the path (see
[SECURITY.md](SECURITY.md#adding-a-secret)). Rotation changes Vault only, no
commit:

```bash
vault login -method=userpass
# Write the new value from stdin, never as an argument
vault kv patch -mount=kv k8s/<namespace>/<secret> <field>=-

# ESO refreshes within refreshInterval (1h); force it now
kubectl -n <namespace> annotate externalsecret <secret> \
  force-sync="$(date +%s)" --overwrite
kubectl -n <namespace> get externalsecret <secret>   # SecretSynced

# Pods read env at start: restart the consumer
kubectl -n <namespace> rollout restart deployment/<app>
```

A value shared by several apps (a database password in
`kv/k8s/postgresql/<app>-db-secret`, the Valkey password) is read from that
one entry by every consumer, so one write updates all of them. The
PostgreSQL databases hook creates roles but never changes an existing role's
password: rotate the role in PostgreSQL as well.

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
`etcd-backup-age` timer on semaphore stopped. `HostBackupStale` means a
backup a host job writes itself (bitwarden's nightly dump and R2 upload) has
no completed run in 26 h; `HostBackupMetricMissing` means the `backup-age`
timer on that host stopped. `HostSystemdUnitFailed` also covers the weekly
`docker-prune` timer on the Docker hosts.

Placement: `WorkersUnbalanced` (requested memory differs by more than 20
points between workers for 36 h, so the nightly descheduler runs did not
level them) and `CoreDNSReplicasOnOneNode` (both CoreDNS replicas on one
node for 26 h). See [Workload Balance](#workload-balance).

ArgoCD: `ArgoAppUnhealthy` (an app not Healthy or Progressing for 15 min),
`ArgoAppSyncFailed` (a sync ended Error or Failed) and `ArgoAutoSyncStuck`
(an auto-sync app OutOfSync for 30 min). Manually synced apps sit OutOfSync
after a push by design, so they never raise the last one.

Firing alerts and silences: <https://alertmanager.example.com> (LAN only).
Scrape targets: <https://prometheus.example.com/targets>. etcd is scraped on
2383 with the `etcd-client-cert` client certificate (CN=prometheus, issued
from the Talos etcd CA, valid until 2036-11-01).

## Workload Balance

The scheduler places a pod once, on the worker with the most unrequested
CPU and memory; nothing moves it afterwards. Two CronJobs in
`apps/infra/descheduler/` repair placement every night (details in
[INFRASTRUCTURE.md](INFRASTRUCTURE.md#descheduler)):

- `descheduler`, 04:00-04:45: moves pods off the worker whose requested
  memory sits more than 5 points above the worker mean, while another sits
  5 below it.
- `descheduler-system`, 04:50: splits CoreDNS replicas that share a node.

Both work on resource requests, so every container sets cpu and memory
requests; `validate:apps` fails on one that does not.

After a rolling upgrade or reboot of the workers, check the uncordon and
level the workers at once instead of waiting for 04:00:

```bash
kubectl get nodes   # no SchedulingDisabled left
job=after-drain-$(date +%s)
kubectl -n descheduler create job --from=cronjob/descheduler "$job"
kubectl -n descheduler wait --for=condition=complete "job/$job" --timeout=5m
kubectl -n descheduler logs "job/$job" | grep -E 'classified|Evicted'
```

After a control-plane reboot, check CoreDNS:

```bash
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
kubectl -n kube-system rollout restart deploy/coredns   # if both share a node
```
