# Wiki.js

## Purpose

Wiki.js 3 holds the homelab operator handbook: hardware, network, hosts,
cluster, applications, runbooks and decisions. It is the one place that ties
the repositories together and records what no repository owns.

## Deployment

- Path: `apps/user/wiki/`
- Namespace: `wiki`
- Sync wave: `"6"` (user tier, auto-sync)
- Chart: upstream `oci://ghcr.io/requarks/charts/wiki`, version pinned in
  `kustomization.yaml`
- Route: `https://wiki.example.com` on the `lan` entrypoint only

## Dependencies

- Shared PostgreSQL: database and role `wiki` from `wiki-db-secret` in the
  postgresql chart's `databases:` list. Wiki.js needs PostgreSQL 17 or later
  and creates the `ltree` and `pg_trgm` extensions itself.
- SealedSecret `wiki-secret` (`kryptos/configs/wiki.yaml`): `DB_PASS`
  derived from `postgresql/wiki-db-secret`, plus the first-boot
  `ADMIN_PASS`. Seal it only after the postgresql app has synced the DB
  secret.

## Operations

- Content and uploads live in PostgreSQL, so the nightly `pg_dumpall`
  covers them. The pod has no PVC; `/wiki/data` is a cache on an emptyDir.
- A push-only Git storage target mirrors every page to a private GitLab
  repository as a second copy.
- The first-boot admin password is in the secret:

  ```bash
  kubectl -n wiki get secret wiki-secret \
    -o jsonpath='{.data.ADMIN_PASS}' | base64 -d
  ```

- Instance settings live in the database, not in Git. After a fresh
  install, turn on Admin → Security → Trust Proxy, because sign-in, rate
  limits, the audit log and live collaboration depend on it.
- Claude Code connects to the wiki's MCP server with a personal access
  token that carries the MCP scope:

  ```bash
  claude mcp add --transport http wiki https://wiki.example.com/_mcp \
    --header "Authorization: Bearer <token>"
  ```

- Chart upgrades arrive as Renovate MRs on `kustomization.yaml`. Database
  migrations run on start; the startup probe allows five minutes for them.
