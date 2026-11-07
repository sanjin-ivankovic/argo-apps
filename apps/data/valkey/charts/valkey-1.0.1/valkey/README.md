# Valkey

Single-node Valkey server on the official `valkey/valkey` image, with an
optional nightly RDB snapshot CronJob (`valkey-cli --rdb`) writing rotated
snapshots to a dedicated PVC.

## TL;DR

```bash
helm install valkey \
  oci://registry.example.com/example-org/helm-charts/valkey \
  --set existingSecret=valkey-auth
```

## Introduction

This chart deploys one Valkey instance as a Deployment (strategy `Recreate`)
with a ReadWriteOnce PVC. It is deliberately single-node: no replication, no
Sentinel, and `replicaCount` must stay `1`.

Design notes:

- **AOF persistence, no RDB auto-save.** `appendonly yes` + `save ""` — the
  backup CronJob takes explicit snapshots instead.
- **`noeviction` on purpose.** `maxmemory`/`maxmemory-policy` are not
  configurable defaults here: job queues (BullMQ) and apps that keep real
  state in Valkey require that nothing is silently evicted.
- **Dangerous commands disabled.** `FLUSHDB`/`FLUSHALL` are rename-command'd
  away by default — on a shared instance a stray flush is cross-app data
  loss. Override via `valkey.disableCommands`.
- **Backups double as canaries.** The snapshot job connects through the
  Service with the same auth path as applications.

## Prerequisites

- Kubernetes >= 1.19
- A PV provisioner (or default StorageClass) for persistence
- An existing Secret holding the server password (`existingSecret`)

## Parameters

### Image parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `image.repository` | The Docker repository to pull the image from | `valkey/valkey` |
| `image.tag` | The image tag to use (with pinned digest) | `9.1.1-trixie@sha256:...` |
| `image.pullPolicy` | The logic of image pulling | `IfNotPresent` |
<!-- markdownlint-enable MD013 MD060 -->

### Deployment parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `replicaCount` | Number of replicas; must stay 1 (single-node, RWO volume) | `1` |
| `updateStrategy` | Update strategy; `Recreate` so the old pod releases the volume first | `{type: Recreate}` |
| `priorityClassName` | Kubernetes priority class for the pod | `""` |
<!-- markdownlint-enable MD013 MD060 -->

### Pod spec parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `resources` | Resource requests and limits | populated |
| `nodeSelector` | Node selector for pod placement | `{}` |
| `affinity` | Pod affinity configuration | `{}` |
| `tolerations` | Pod tolerations | `[]` |
| `topologySpreadConstraints` | Topology spread constraints | `[]` |
<!-- markdownlint-enable MD013 MD060 -->

### Security parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `podSecurityContext` | Pod security context (official image's valkey user is uid/gid 999) | non-root 999 |
| `containerSecurityContext` | Container security context (`readOnlyRootFilesystem: true` — valkey only writes /data) | restricted |
<!-- markdownlint-enable MD013 MD060 -->

### Valkey parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `valkey.appendonly` | AOF persistence (RDB auto-save is always off) | `true` |
| `valkey.disableCommands` | Commands disabled via empty rename-command | `[FLUSHDB, FLUSHALL]` |
| `valkey.extraFlags` | Map of extra settings rendered as `--key value` args | `{}` |
<!-- markdownlint-enable MD013 MD060 -->

### Secret parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `existingSecret` | Existing secret with the server password (required — empty means UNAUTHENTICATED) | `""` |
| `secretKeys.password` | Key inside `existingSecret` holding the password | `password` |
<!-- markdownlint-enable MD013 MD060 -->

### Service parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `6379` |
| `service.loadBalancerIP` | Static IP for type LoadBalancer (e.g. MetalLB) | `""` |
| `service.annotations` | Extra service annotations | `{}` |
<!-- markdownlint-enable MD013 MD060 -->

### Persistence parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `persistence.enabled` | Enable the data PVC | `true` |
| `persistence.storageClass` | Storage class; empty uses the cluster default | `""` |
| `persistence.size` | PVC size | `8Gi` |
| `persistence.accessModes` | PVC access modes | `[ReadWriteOnce]` |
| `persistence.mountPath` | Volume mount path (the image's data directory) | `/data` |
<!-- markdownlint-enable MD013 MD060 -->

### Probe parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `probes.startup.*` | `valkey-cli ping` startup probe; budget covers AOF replay | enabled, 30x5s |
| `probes.liveness.*` | `valkey-cli ping` liveness probe | enabled |
| `probes.readiness.*` | `valkey-cli ping` readiness probe | enabled |
<!-- markdownlint-enable MD013 MD060 -->

### Backup parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `backup.enabled` | Nightly RDB snapshot CronJob to a dedicated PVC | `false` |
| `backup.schedule` | Cron schedule | `30 3 * * *` |
| `backup.retention` | Most recent snapshots to keep | `7` |
| `backup.activeDeadlineSeconds` | Hard runtime limit per job | `1800` |
| `backup.startingDeadlineSeconds` | How late a missed schedule may start | `600` |
| `backup.successfulJobsHistoryLimit` | Completed jobs kept | `3` |
| `backup.failedJobsHistoryLimit` | Failed jobs kept | `3` |
| `backup.resources` | Backup pod resources (populated: ResourceQuota namespaces reject request-less pods) | populated |
| `backup.persistence.*` | Backup PVC (storageClass/size/accessModes) | `5Gi` |
<!-- markdownlint-enable MD013 MD060 -->

## Restore

Snapshots are standard RDB files, gzipped. To restore: stop writers, place
the decompressed file as `dump.rdb` in `/data` of a server started with
`--appendonly no` (AOF takes precedence over RDB at boot), let it load, then
re-enable AOF with `BGREWRITEAOF` + config change. For cache-tier data it is
usually simpler to re-seed.
