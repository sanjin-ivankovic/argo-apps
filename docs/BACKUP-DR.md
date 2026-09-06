# Backup & Disaster Recovery

This document separates what GitOps recreates automatically from what
requires real data recovery, and gives a minimum recovery order.

## Table of Contents

- [What GitOps Recreates](#what-gitops-recreates)
- [What Requires Data Recovery](#what-requires-data-recovery)
- [The Sealed-Secrets Key](#the-sealed-secrets-key)
- [Minimum Recovery Order](#minimum-recovery-order)

## What GitOps Recreates

Everything declarative in this repository is recreated by re-bootstrapping
ArgoCD. No separate backup is needed for:

- The root Application and ApplicationSet (`argocd/root.yaml`,
  `argocd/apps-set.yaml`).
- Every app's manifests, Kustomize overlays, and Helm values under
  `apps/<tier>/<app>/`.
- SealedSecret **ciphertext** in `apps/<tier>/<app>/secrets/` (safe to
  commit; only decryptable by the cluster's sealed-secrets key).
- Traefik IngressRoutes, middlewares, and the cert-manager configuration
  that re-issues TLS certificates.

## What Requires Data Recovery

These hold state that does **not** live in Git and must be restored from a
backup or recreated:

- **PostgreSQL** (`apps/data/postgresql`) — the shared cluster backing
  Harbor, DocuSeal, Joplin, LiteLLM, Memos, SnapOtter, and Authentik.
  Per-app databases are provisioned by the manual jobs in
  `apps/data/postgresql/jobs/` (not ArgoCD-tracked). The `authentik`
  database pairs with the immutable `AUTHENTIK_SECRET_KEY` in its
  SealedSecret — DB and key together are the recovery unit; losing the key
  invalidates every session.

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
- **Valkey** (`apps/data/valkey`) — cache for SearXNG (db 1, disposable)
  and SnapOtter's job queues (db 2), but **OneTimeSecret keeps ALL of its
  state in db 3** (accounts and every live one-time link) — treat Valkey as
  a real datastore, not just cache.

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

## The Sealed-Secrets Key

The sealed-secrets controller's private key (in `kube-system`) is the single
most important thing to back up. Without it, committed SealedSecret
ciphertext **cannot** be decrypted and every secret must be regenerated and
resealed via [SECURITY.md](SECURITY.md) and the kryptos configs.

Back up the controller key separately and securely (never in this repo). If
the key is lost, the recovery path is: re-seal all secrets from
`kryptos/configs/` against the new key, then commit and sync.

## Minimum Recovery Order

1. Restore the Kubernetes control plane and Longhorn storage.
2. Restore the **sealed-secrets controller key** into `kube-system` (or
   accept resealing everything).
3. Apply `argocd/root.yaml` to bootstrap ArgoCD.
4. Sync the ApplicationSet, then sync apps in sync-wave order
   (infra `-1..3` -> data `4` -> services `5` -> user `6`). See
   [ARCHITECTURE.md](ARCHITECTURE.md).
5. Restore PostgreSQL from the newest `postgresql-backups` dump (see
   above) / Valkey / Longhorn data; re-run the
   `apps/data/postgresql/jobs/` DB-create jobs only for databases that no
   longer exist.
6. Validate routes and certificates:
   `kubectl get ingressroute -A`, `kubectl get certificates -A`.
