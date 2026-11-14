# Backup & Disaster Recovery

This document separates what GitOps recreates automatically from what
requires real data recovery, and gives a minimum recovery order.

## Table of Contents

- [What GitOps Recreates](#what-gitops-recreates)
- [What Requires Data Recovery](#what-requires-data-recovery)
- [Secret Values in Vault](#secret-values-in-vault)
- [Minimum Recovery Order](#minimum-recovery-order)

## What GitOps Recreates

Everything declarative in this repository is recreated by re-bootstrapping
ArgoCD. No separate backup is needed for:

- The root Application and ApplicationSet (`argocd/root.yaml`,
  `argocd/apps-set.yaml`).
- Every app's manifests, Kustomize overlays, and Helm values under
  `apps/<tier>/<app>/`.
- The `ExternalSecret` references in `apps/<tier>/<app>/secrets/`. They hold
  Vault paths only; the values are recovered with Vault (below).
- Traefik IngressRoutes, middlewares, and the cert-manager configuration
  that re-issues TLS certificates.

## What Requires Data Recovery

These hold state that does **not** live in Git and must be restored from a
backup or recreated:

- **PostgreSQL** (`apps/data/postgresql`) — the shared cluster backing
  Harbor, Docmost, DocuSeal, OpenGist, and Authentik.
  Docmost keeps pages, history and labels in its database; its attachments
  sit on the `docmost-data` volume, which has no off-cluster copy.
  Per-app databases are provisioned by the chart's PostSync hook from
  `databases:` in `apps/data/postgresql/values.yaml`. The `authentik`
  database pairs with the immutable `AUTHENTIK_SECRET_KEY` in Vault
  (`kv/k8s/authentik/authentik-secret`) — DB and key together are the
  recovery unit; losing the key invalidates every session.

  Nightly backups exist: the `postgresql-backup` CronJob (03:00) writes
  gzipped `pg_dumpall --clean --if-exists` dumps to the `postgresql-backups`
  PVC (20Gi, Longhorn), keeping the 7 most recent. Restore into a fresh
  server:

  ```bash
  PGPW=$(kubectl -n postgresql get secret postgresql-secret \
    -o jsonpath='{.data.postgres-password}' | base64 -d)
  # copy the dump off the backup PVC via a throwaway pod, then:
  gunzip -c pg_dumpall-<ts>.sql.gz | kubectl -n postgresql exec -i \
    deploy/postgresql -- env PGPASSWORD="$PGPW" psql -U postgres -f -
  ```

  The dumps include roles with password hashes, so consumer credentials
  survive a restore unchanged.
- **Valkey** (`apps/data/valkey`) — cache for SearXNG (db 1, disposable),
  Docmost's queues and collaboration state (db 2, rebuilt from PostgreSQL),
  but **OneTimeSecret keeps ALL of its state in db 3** (accounts and every
  live one-time link) — treat Valkey as a real datastore, not just cache.
  Every other db index is unassigned.

  Nightly backups exist: the `valkey-primary-backup` CronJob (03:30) takes
  an RDB snapshot over the network to the `valkey-primary-backups` PVC
  (5Gi, Longhorn), keeping the 7 most recent. To restore selected data into
  a running server, load the snapshot in a throwaway valkey pod and
  `MIGRATE` the needed keys (per-database) with `COPY REPLACE AUTH`; for
  cache-tier databases it is usually simpler to let them rebuild.
- **Longhorn volumes / PVCs** — all persistent workload data.
- **Harbor** registry storage.
- **External service state** — anything proxied via
  `apps/infra/external-services` lives outside the cluster and is recovered
  by its own owner.

## Secret Values in Vault

Every app Secret is built by the External Secrets Operator from HashiCorp
Vault (`kv/k8s/<namespace>/<secret>`). Vault runs outside the cluster, on the
`vault` LXC (ct/416); its runbook is proxmox-infra `docs/VAULT.md`. Git holds
no secret values and no ciphertext.

The recovery unit is two things together:

- **The Raft snapshot**: a timer on the vault LXC saves one at 02:00 to
  `/var/backups/vault`; the PBS backup of ct/416 and its offsite copy carry
  it. The data is encrypted by Vault's barrier.
- **The unseal key shares** (3 shares, threshold 2), kept in Bitwarden.
  Without them a restored snapshot cannot be unsealed.

Vault's `kubernetes` auth method trusts the cluster's CA (proxmox-infra
`terraform/vault`). A rebuilt cluster with a new CA needs that value updated
and applied, or ESO's login fails with 403 and no Secret is created.

## Minimum Recovery Order

1. Restore the Kubernetes control plane and Longhorn storage.
2. Make sure **Vault** is up and unsealed (restore its LXC or snapshot if
   needed), and that its `kubernetes` auth trusts the cluster's CA.
3. Apply `argocd/root.yaml` to bootstrap ArgoCD.
4. Sync the ApplicationSet, then sync apps in sync-wave order
   (infra `-1..3` -> data `4` -> services `5` -> user `6`). See
   [ARCHITECTURE.md](ARCHITECTURE.md).
5. Restore PostgreSQL from the newest `postgresql-backups` dump (see
   above) / Valkey / Longhorn data. A postgresql sync re-runs the database
   hook, which creates only the databases that no longer exist.
6. Validate routes and certificates:
   `kubectl get ingressroute -A`, `kubectl get certificates -A`.
