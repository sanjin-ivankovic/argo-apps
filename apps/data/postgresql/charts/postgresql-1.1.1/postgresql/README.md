# PostgreSQL

Single-node PostgreSQL server on the official `docker.io/library/postgres`
image, with an optional nightly `pg_dumpall` backup CronJob writing rotated
dumps to a dedicated PVC, and optional per-application database provisioning.

## TL;DR

```bash
helm install postgresql \
  oci://registry.example.com/example-org/helm-charts/postgresql \
  --set existingSecret=postgresql-secret
```

## Introduction

This chart deploys one PostgreSQL instance as a Deployment (strategy
`Recreate`) with a ReadWriteOnce PVC. It is deliberately single-node: there is
no replication, and `replicaCount` must stay `1` — two postmasters must never
open the same data directory.

Design notes:

- **Official image, Debian variant.** musl (alpine) has no real locale
  support, and swapping libc changes collation order — dangerous for existing
  indexes. The image is pinned by tag+digest.
- **Version-independent PGDATA.** Since PostgreSQL 18 the official image
  defaults `PGDATA` to a major-versioned path
  (`/var/lib/postgresql/18/docker`), so a major image bump would silently boot
  an empty cluster. This chart mounts the volume at `/var/lib/postgresql` and
  pins `PGDATA=/var/lib/postgresql/data/pgdata`.
- **Major upgrades are manual.** A PostgreSQL major version is a data-format
  migration: dump, deploy fresh, restore. Never bump the image major in place.
- **Backups double as canaries.** The backup CronJob connects through the
  Service with the same auth path as applications, so a failing nightly backup
  also signals a broken server or credential.

## Prerequisites

- Kubernetes >= 1.19
- A PV provisioner (or default StorageClass) for persistence
- An existing Secret holding the superuser password (`existingSecret`)

## Parameters

### Image parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `image.repository` | The Docker repository to pull the image from | `postgres` |
| `image.tag` | The image tag to use (with pinned digest) | `18.6-trixie@sha256:...` |
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
| `podSecurityContext` | Pod security context (official image's postgres user is uid/gid 999) | non-root 999 |
| `containerSecurityContext` | Container security context (`readOnlyRootFilesystem: true`; /run/postgresql and /tmp are emptyDir mounts) | restricted |
<!-- markdownlint-enable MD013 MD060 -->

### PostgreSQL parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `postgresql.pgData` | Data directory inside the volume (version-independent, see Introduction) | `/var/lib/postgresql/data/pgdata` |
| `postgresql.initdbArgs` | Extra initdb arguments, first boot only (e.g. `--encoding=UTF8 --locale=en_US.UTF-8`) | `""` |
| `postgresql.extraArgs` | Map of postgresql.conf settings rendered as `-c key=value` args | `{}` |
<!-- markdownlint-enable MD013 MD060 -->

### Secret parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `existingSecret` | Existing secret with the superuser password (required for real deployments) | `""` |
| `secretKeys.adminPassword` | Key inside `existingSecret` holding the postgres password | `postgres-password` |
<!-- markdownlint-enable MD013 MD060 -->

### Service parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `5432` |
| `service.loadBalancerIP` | Static IP for type LoadBalancer (e.g. MetalLB) | `""` |
| `service.annotations` | Extra service annotations | `{}` |
<!-- markdownlint-enable MD013 MD060 -->

### Persistence parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `persistence.enabled` | Enable the data PVC | `true` |
| `persistence.storageClass` | Storage class; empty uses the cluster default | `""` |
| `persistence.size` | PVC size | `16Gi` |
| `persistence.accessModes` | PVC access modes | `[ReadWriteOnce]` |
| `persistence.mountPath` | Volume mount path (PG 18+ image VOLUME location) | `/var/lib/postgresql` |
<!-- markdownlint-enable MD013 MD060 -->

### Shared memory parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `shmVolume.enabled` | Mount an in-memory emptyDir over /dev/shm (k8s default 64Mi is too small) | `true` |
| `shmVolume.sizeLimit` | Size limit of the /dev/shm emptyDir | `256Mi` |
<!-- markdownlint-enable MD013 MD060 -->

### Probe parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `probes.startup.*` | `pg_isready` startup probe; budget covers crash-recovery WAL replay | enabled, 30x5s |
| `probes.liveness.*` | `pg_isready` liveness probe | enabled |
| `probes.readiness.*` | `pg_isready` readiness probe | enabled |
<!-- markdownlint-enable MD013 MD060 -->

### Backup parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `backup.enabled` | Nightly `pg_dumpall` CronJob to a dedicated PVC | `false` |
| `backup.schedule` | Cron schedule | `0 3 * * *` |
| `backup.retention` | Most recent dumps to keep | `7` |
| `backup.activeDeadlineSeconds` | Hard runtime limit per job | `3600` |
| `backup.startingDeadlineSeconds` | How late a missed schedule may start | `600` |
| `backup.successfulJobsHistoryLimit` | Completed jobs kept | `3` |
| `backup.failedJobsHistoryLimit` | Failed jobs kept | `3` |
| `backup.resources` | Backup pod resources (populated: ResourceQuota namespaces reject request-less pods) | populated |
| `backup.persistence.*` | Backup PVC (storageClass/size/accessModes) | `20Gi` |
<!-- markdownlint-enable MD013 MD060 -->

### Database provisioning parameters

<!-- markdownlint-disable MD013 MD060 -->
| Name | Description | Value |
| ---- | ----------- | ----- |
| `databases` | List of `{secretName}`; each Secret (release namespace) holds one application's database name, owner role and password | `[]` |
| `databaseJob.secretKeys.*` | Keys for the database name, owner role and password inside each Secret | `database`, `username`, `password` |
| `databaseJob.backoffLimit` | Retries of the provisioning Job | `3` |
| `databaseJob.activeDeadlineSeconds` | Hard runtime limit for the provisioning Job | `600` |
| `databaseJob.resources` | Provisioning pod resources (populated for ResourceQuota namespaces) | populated |
<!-- markdownlint-enable MD013 MD060 -->

## Database provisioning

With `databases` set, a `post-install,post-upgrade` hook Job runs after every
install and upgrade (ArgoCD runs it as `PostSync` on every sync). For each
listed Secret it creates the owner role and the database when they are
missing, and reasserts the database owner. It never changes an existing
role's password and never drops anything, so running it again is a no-op.

A listed Secret that does not exist yet (for example, a SealedSecret not yet
unsealed) is reported by name and fails the Job once every other entry is
done; the next sync retries it. The last run is kept until the next one
replaces it:

```bash
kubectl -n <ns> logs job/<release>-databases
```

## Restore

Dumps are plain `pg_dumpall --clean --if-exists` output, gzipped. To restore
into a fresh server:

```bash
gunzip -c pg_dumpall-<ts>.sql.gz | kubectl -n <ns> exec -i \
  deploy/postgresql -- env PGPASSWORD=... psql -U postgres -f -
```
