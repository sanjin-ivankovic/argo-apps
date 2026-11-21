# Actual

## Purpose

Actual Budget, a local-first personal budgeting app. The sync server serves
the web client and keeps budget files in sync across browsers and devices.

## Deployment

- Path: `apps/user/actual/`
- Namespace: `actual`
- Sync wave: `"6"` (user tier, auto-sync)
- Chart: homelab `actual` from `oci://registry.example.com/example-org/helm-charts`
  (helm-charts `charts/actual/`), version pinned in `kustomization.yaml`
- Route: `https://actual.example.com` on the `lan` entrypoint only, Actual's
  own server password, no ForwardAuth. ForwardAuth in front of Actual breaks
  the client's `/sync` requests once the auth session expires.

## Dependencies

- None: no database, no Secret. All state lives on the `actual-data`
  volume (2Gi, Longhorn): `server-files/account.sqlite` (password hash,
  sessions, file list) and `user-files/` (budget files).

## Operations

- First visit to `https://actual.example.com` sets the server password.
- Reset a forgotten password from inside the pod. The script needs a
  terminal, so keep `-it`. Changing the password signs out every session.

  ```bash
  kubectl -n actual exec -it deploy/actual -- \
    node /app/scripts/reset-password.js
  ```

- The `actual-data` volume has no off-cluster copy. The only backup is a
  per-budget export from the UI (Settings, Export data), which can be
  re-imported into a fresh server.
- Upgrades are chart bumps (Renovate). Database migrations run at start,
  before the server listens; the liveness probe allows about 2.5 minutes.
