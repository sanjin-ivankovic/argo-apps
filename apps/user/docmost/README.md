# Docmost

## Purpose

Docmost holds the homelab operator handbook: hardware, network, hosts,
cluster, applications, runbooks and decisions, in one space `Handbook`.
People edit in the browser; Claude Code reads and writes through the
`docmost` server of the homelab MCP plugin (mcp-plugins).

## Deployment

- Path: `apps/user/docmost/`
- Namespace: `docmost`
- Sync wave: `"6"` (user tier, auto-sync)
- Chart: homelab `docmost` from `oci://registry.example.com/example-org/helm-charts`
  (helm-charts `charts/docmost/`), version pinned in `kustomization.yaml`
- Route: `https://docmost.example.com` on the `lan` entrypoint only, Docmost's
  own login, no ForwardAuth

## Dependencies

- Shared PostgreSQL: database and role `docmost` from `docmost-db-secret` in
  the postgresql chart's `databases:` list. Migrations run at every start and
  create the `unaccent` and `pg_trgm` extensions as the database owner.
- Shared Valkey, db 2: queues and collaboration state.
- ExternalSecret `docmost-secret` (`secrets/docmost-external-secret.yaml`):
  `APP_SECRET` from Vault `kv/k8s/docmost/docmost-secret`; `DATABASE_URL`
  rendered from `kv/k8s/postgresql/docmost-db-secret`; `REDIS_URL` rendered
  from `kv/k8s/valkey/valkey-auth`.

## Operations

- Pages, history and labels live in PostgreSQL, so the nightly `pg_dumpall`
  covers them. Attachments live on the `docmost-data` volume, which has no
  off-cluster copy.
- Changing `APP_SECRET` logs every user out.
- Settings that live only in the database and need redoing after a fresh
  install: the workspace and owner (`/setup/register`), the space
  `Handbook` (slug `handbook`), and the member `claude` that the MCP server
  logs in as, added to that space as a writer. No mail is configured;
  invitations are shared by copying the invite link from Settings, Members.
- The MCP server uses Docmost's internal API, which can change between
  releases (API keys are a paid feature). After a Docmost version bump, run
  `docmost_search_pages`, `docmost_get_page` and one `docmost_update_page` on
  a scratch page before calling the bump done.
- At every start Docmost rewrites its client `index.html`; the chart's
  `client-dist` init container gives it a writable copy, so the root
  filesystem stays read-only.
