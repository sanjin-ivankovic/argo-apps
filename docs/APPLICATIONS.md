# Applications

This document provides a comprehensive catalog of all deployed applications
and guides for managing them.

## Table of Contents

- [Overview](#overview)
- [Active Applications](#active-applications)
- [Application Details](#application-details)
- [Shared Infrastructure](#shared-infrastructure)
- [Adding a New Application](#adding-a-new-application)

## Overview

The platform runs a curated set of user-facing applications spanning
document management, developer tools, note-taking, search, secret sharing,
file and PDF processing, and LLM tooling.

**Application Discovery**: Apps are managed by a single ArgoCD ApplicationSet
([argocd/apps-set.yaml](../argocd/apps-set.yaml)) using a Git **files**
generator (`path: apps/*/*/config.yaml`). Every app — infrastructure and
user-facing alike — lives under `apps/<tier>/<app>/` and declares its own
metadata in a `config.yaml`. Add a new app by creating its directory **and**
a `config.yaml`; without that file the ApplicationSet will not generate an
Application for it.

**Common Patterns**:

- 🔧 **Helm charts** from custom OCI registry or public repos
- 🌐 **Traefik IngressRoute** for HTTPS ingress
- 🔐 **ExternalSecrets** for credentials (values in HashiCorp Vault)
- 💾 **Longhorn storage** for persistent data
- 🏷️ **Priority classes** for resource scheduling

## Active Applications

<!-- markdownlint-disable MD013 MD060 -->
| Application            | Description                  | Chart Source  | Version  | Ingress | Secrets |
| ---------------------- | ---------------------------- | ------------- | -------- | ------- | ------- |
| **Docmost**            | Homelab operator handbook    | Custom OCI    | 1.0.1    | ✅      | ✅      |
| **DocuSeal**           | Document signing platform    | Custom OCI    | 1.0.8    | ✅      | ✅      |
| **Harbor**             | OCI registry                 | Public Helm   | 1.19.2   | ✅      | ✅      |
| **Headlamp**           | Kubernetes management UI     | Public Helm   | 0.44.0   | ✅      | ✅      |
| **ntfy**               | Push notifications           | Custom OCI    | 1.0.0    | ✅      | ✅      |
| **Obsidian**           | Notes desktop + LiveSync     | Custom OCI    | 1.0.0    | ✅      | ✅      |
| **OpenGist**           | Git-backed snippets          | Custom OCI    | 1.0.0    | ✅      | ✅      |
| **OneTimeSecret**      | View-once secret links       | Custom OCI    | 1.0.2    | ✅      | ✅      |
| **PostgreSQL**         | Shared database cluster      | Custom OCI    | 1.0.0    | ❌      | ✅      |
| **PrivateBin**         | Encrypted pastebin           | Custom OCI    | 1.2.0    | ✅      | ❌      |
| **SearXNG**            | Privacy-focused metasearch   | Custom OCI    | 1.1.2    | ✅      | ✅      |
| **Stirling-PDF**       | Self-hosted PDF toolset      | Custom OCI    | 1.1.0    | ✅      | ❌      |
| **Valkey**             | Redis-compatible cache       | Custom OCI    | 1.0.0    | ❌      | ✅      |
<!-- markdownlint-enable MD013 MD060 -->

**Chart Sources**:

- **Custom OCI**: `oci://registry.example.com/example-org/helm-charts` - Custom
  charts from [helm-charts](https://source.example.com/example-org/helm-charts.git)
- **Public Helm**: Standard upstream repositories

## Application Details

### Docmost

**Description**: Docmost, the homelab operator handbook

**Location**: `apps/user/docmost/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/docmost`
(version pinned in the app kustomization)

**URL**: `https://docmost.example.com` (LAN only)

**Database**: PostgreSQL (shared cluster). Migrations run at every start
and create the `unaccent` and `pg_trgm` extensions as the database owner.
Pages, history and labels live in the database; attachments on the 5Gi
volume. Valkey db 2 holds queues and collaboration state

**Credentials**: ExternalSecret `docmost-secret` from Vault: `APP_SECRET`
from `kv/k8s/docmost/docmost-secret` (a new value logs everyone out),
`DATABASE_URL` rendered from `kv/k8s/postgresql/docmost-db-secret`, and
`REDIS_URL` rendered from `kv/k8s/valkey/valkey-auth`

**Notes**: built-in login, no Authentik (SSO is a paid Docmost feature).
Claude Code writes pages through the `docmost` server of the homelab MCP
plugin, which logs in as the member `claude` and uses Docmost's internal
API; run its smoke test after every Docmost version bump

---

### DocuSeal

**Description**: Open-source document signing and form-filling platform

**Purpose**: Self-hosted e-signature workflows

**Location**: `apps/user/docuseal/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/docuseal`
(version pinned in the app kustomization)

**URL**: `https://docuseal.example.com`

**Database**: PostgreSQL (shared cluster)

**Features**:

- Document templates and signing flows
- Form fields and signatures
- PostgreSQL-backed storage

**Configuration**:

- PostgreSQL database: `docuseal` on shared cluster
- Persistent storage via Longhorn PVC

**Credentials**: ExternalSecret `docuseal-secret` from Vault
`kv/k8s/docuseal/docuseal-secret`: `DATABASE_URL` (stored as rendered) and
`SECRET_KEY_BASE`, which must never change

---

### Harbor

**Description**: OCI registry for container images and Helm charts

**Location**: `apps/services/harbor/`

**Chart**: `https://helm.goharbor.io/harbor`
(version pinned in the app kustomization)

**URL**: `https://registry.example.com` (also `registry.example.com`)

**Database**: PostgreSQL (shared cluster); Redis is the chart-bundled
internal instance, not the shared Valkey

**Artifact retention**: never delete artifacts by hand. Several repos pin
internal images by digest (`ci-components/ci:latest@sha256:...` in the CI
image Dockerfiles, `proxmox-infra/ci:latest@sha256:...` in the semaphore
image), and Renovate moves those pins only after a 3-day soak. A digest
deleted inside that window breaks every build of the old pin. The `homelab`
project's tag retention policy (Harbor UI, Policy > Tag Retention; not in
Git) does the pruning instead; an artifact is kept if any rule keeps it:

| Repositories | Tags | Keeps |
| --- | --- | --- |
| `helm-charts/*` | `**` | always |
| `kryptos/cli`, `ci-bootstrap` | `**` | always |
| `**` | `**`, untagged included | pushed within the last 14 days |
| `**` | `**` | the 3 most recently pushed (per repository) |

Charts are pinned by version in argo-apps, and `kryptos/cli` holds the only copy
of the retired kryptos release binaries, so neither is pruned. A rule takes
either a matching or an excluding repository list, not both, so `helm-charts/*`
(one `*` stops at `/`) also keeps every `helm-charts/ci` image; listing charts
by name would leave a new chart unprotected. The policy runs daily; garbage
collection (Administration > Clean Up) runs weekly after it and frees the space.
Run the policy's dry run after any rule change.

---

### Headlamp

**Description**: Kubernetes management UI (cluster dashboard)

**Location**: `apps/services/headlamp/`

**Chart**: `https://kubernetes-sigs.github.io/headlamp/headlamp`
(version pinned in the app kustomization)

**URL**: `https://headlamp.example.com`

**Authentication**: Authentik OIDC client; the Kubernetes apiserver
validates the issued tokens for per-user RBAC

---

### Obsidian

**Description**: The Obsidian desktop app streamed to the browser
(linuxserver.io Selkies image), plus a single-node CouchDB for the
Self-hosted LiveSync plugin

**Location**: `apps/user/obsidian/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/obsidian`
(version pinned in the app kustomization)

**URLs**:

- `https://obsidian.example.com`: the desktop; `lan` only, reached from
  outside over WireGuard, behind the image's basic auth.
- `https://couchdb.example.com`: CouchDB for LiveSync devices; `lan` only,
  CouchDB basic auth. The desktop itself syncs over the Service
  `obsidian-couchdb.obsidian.svc.cluster.local:5984`.

**Storage**: PVCs `obsidian-config` (10 GiB, `/config`: vaults, plugins,
settings) and `obsidian-couchdb-data` (10 GiB)

**Credentials**: ExternalSecrets from Vault, keys `username` and `password`:
`obsidian-auth-secret` (`kv/k8s/obsidian/obsidian-auth-secret`, desktop
login) and `obsidian-couchdb-secret`
(`kv/k8s/obsidian/obsidian-couchdb-secret`, CouchDB admin, also used by
LiveSync clients)

**Notes**: LiveSync on phones and laptops needs CORS preflights to reach
CouchDB, which answers them for `app://obsidian.md` and
`capacitor://localhost`; Traefik's headers middleware therefore sets no
CORS options. Turn on LiveSync end-to-end encryption.

---

### ntfy

**Description**: Push notifications for Komodo alerts, GitLab pipelines and
Unraid backups (zerobyte)

**Location**: `apps/user/ntfy/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/ntfy`
(version pinned in the app kustomization)

**URL**: `https://ntfy.example.com` (LAN only; phones off the LAN use
WireGuard)

**Access**: `auth-default-access: deny-all`. `maintainer` (admin) reads every
topic. `komodo`, `gitlab` and `zerobyte` each publish with a token,
write-only to `komodo-alerts`, `gitlab-pipelines` and `unraid-backups`.
iOS push goes through ntfy.sh as a poll request carrying only the message ID.

**Credentials**: ExternalSecret `ntfy-secret` from Vault
`kv/k8s/ntfy/ntfy-secret`: the declarative users (bcrypt) and tokens ntfy
reconciles on every start, plus `maintainer_password`, `komodo_token`,
`gitlab_token`, `zerobyte_token` and `alertmanager_token` for the clients.
`NTFY_AUTH_USERS` and `NTFY_AUTH_TOKENS` are stored as rendered; a changed
token has to change there too, and in its client

---

### OneTimeSecret

**Description**: Expiring, view-once secret links

**Location**: `apps/user/onetimesecret/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/onetimesecret`
(version pinned in the app kustomization)

**URL**: `https://secret.example.com`

**Cache**: Valkey (shared cluster) holds all state

**Credentials**: ExternalSecret `onetimesecret-secret` from Vault
`kv/k8s/onetimesecret/onetimesecret-secret`: `SECRET`, which must never
change, and `REDIS_URL` (stored as rendered)

---

### OpenGist

**Description**: Git-backed snippet store; the path for scripts to the work
machine, whose proxy strips WebSocket upgrades (OpenGist is plain HTTP)

**Location**: `apps/user/opengist/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/opengist`
(version pinned in the app kustomization)

**URL**: `https://gist.example.com` (`lan` ungated; `public` behind
`authentik-forwardauth` in front of OpenGist's own login)

**Database**: PostgreSQL (shared cluster); gist content is Git repositories
on the 5Gi volume

**Credentials**: ExternalSecret `opengist-secret` from Vault:
`OG_SECRET_KEY` from `kv/k8s/opengist/opengist-secret` (change only on
purpose: a new key logs everyone out) and `OG_DB_URI`, rendered from
`kv/k8s/postgresql/opengist-db-secret`

---

### PostgreSQL

**Description**: Shared PostgreSQL 18 database cluster

**Purpose**: Central database for applications (Harbor, DocuSeal,
Docmost, OpenGist, Authentik)

**Location**: `apps/data/postgresql/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/postgresql`
(version pinned in the app kustomization; the chart is VENDORED at
`apps/data/postgresql/charts/` because its OCI source is the in-cluster
Harbor, which depends on this database)

**Features**:

- PostgreSQL 18.x (official `docker.io/library/postgres` image, Debian
  variant, digest-pinned)
- Persistent storage via Longhorn
- Nightly `pg_dumpall` backups (see Backups below)
- Priority class: `high-priority-stateful`

**Database Creation**:

The chart's PostSync hook Job (`postgresql-databases`) runs on every sync of
the postgresql app. For each Secret listed under `databases:` in
`apps/data/postgresql/values.yaml` it creates the owner role and the
database when missing and reasserts the owner. It never changes an existing
role's password and never drops anything. The list holds one
`<app>-db-secret` per consumer below.

**Consumers**:

- **Harbor** (services tier)
- **Authentik** (infrastructure component)
- **Docmost** (application)
- **DocuSeal** (application)
- **OpenGist** (application)

**Connection Details**:

- **Host**: `postgresql.postgresql.svc.cluster.local`
- **Port**: `5432`
- **Superuser**: `postgres` (ExternalSecret `postgresql-secret`)
- **Application users**: Created by database jobs

**Credentials**:

ExternalSecrets from Vault, `kv/k8s/postgresql/<secret>`: the superuser's
`postgresql-secret` and one `<app>-db-secret` per database (`username`,
`password`, `database`). The apps read their password from the same entry

**Backups**:

A CronJob (`postgresql-backup`, 03:00 nightly) writes gzipped
`pg_dumpall --clean --if-exists` dumps to the dedicated 20Gi
`postgresql-backups` PVC, keeping the 7 most recent. Trigger one manually:

```bash
kubectl -n postgresql create job --from=cronjob/postgresql-backup backup-manual
```

Restore procedure: [BACKUP-DR.md](BACKUP-DR.md).

---

### PrivateBin

**Description**: Zero-knowledge encrypted pastebin

**Purpose**: Securely share text snippets, code, logs and log files, for
example from the work machine to home

**Location**: `apps/user/privatebin/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/privatebin`
(version pinned in the app kustomization)

**URL**: `https://privatebin.example.com`

**Features**:

- Client-side encryption (server never sees plaintext)
- Password protection
- File attachments up to 10 MiB of encrypted data per paste (`config` in
  the app values; the image's nginx and PHP cap requests at 15 MB)
- Burn after reading
- Syntax highlighting

**Storage**: Filesystem backend (Longhorn PVC)

---

### SearXNG

**Description**: Privacy-respecting metasearch engine

**Purpose**: Search aggregator without tracking or ads

**Location**: `apps/user/searxng/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/searxng`
(version pinned in the app kustomization)

**URL**: `https://search.example.com`

**Search Engines Aggregated**:

- Google, Bing, DuckDuckGo
- Wikipedia, Yahoo
- GitHub, StackOverflow
- Specialty engines (academic, images, videos)

**Cache**: Valkey (Redis backend)

**Configuration**:

- Rate limiting: Valkey-backed
- Result caching: 1 hour TTL
- No logging of search queries
- No search history stored

**Credentials**: ExternalSecret `searxng-app` from Vault
`kv/k8s/searxng/searxng-app`; `valkey-password` is read from
`kv/k8s/valkey/valkey-auth`

---

### Stirling-PDF

**Description**: Self-hosted PDF toolset

**Location**: `apps/user/stirling-pdf/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/stirling-pdf`
(version pinned in the app kustomization)

**URL**: `https://pdf.example.com`

**Credentials**: ExternalSecret `stirling-pdf-secret`:
`SECURITY_OAUTH2_CLIENTSECRET` from Vault
`kv/k8s/authentik/authentik-oidc-clients`

**Notes**: login is Authentik OIDC (`stirling-pdf` client, `admins`
group), so the IngressRoute carries no ForwardAuth middleware. Password
login is off (`SECURITY_LOGINMETHOD: oauth2`) and the login page redirects
straight to Authentik. New SSO users start with the standard role; an
Authentik-backed Admin promotes them under Settings → Workspace → Users.
Break-glass for the local admin: set `SECURITY_LOGINMETHOD` back to `all`.

---

### Valkey

**Description**: Redis-compatible in-memory data store (Redis fork by
Linux Foundation)

**Purpose**: Shared cache/data store for applications (SearXNG, Docmost
and OneTimeSecret)

**Location**: `apps/data/valkey/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/valkey`
(version pinned in the app kustomization; the chart is VENDORED at
`apps/data/valkey/charts/` because its OCI source is the in-cluster Harbor)

**Features**:

- Valkey (official `valkey/valkey` image, Debian variant, digest-pinned)
- AOF persistence to Longhorn PVC (RDB auto-save off)
- Nightly RDB snapshot backups (see Backups below)
- Priority class: `high-priority-stateful`

**Consumers** (logical database allocation: 1, 2 and 3 assigned, every
other index free):

- **SearXNG** (db 1) - Search result caching and rate limiting
- **Docmost** (db 2) - BullMQ queues and collaboration state
- **OneTimeSecret** (db 3) - Primary data store (ALL state: links + accounts)

**Connection Details**:

- **Host**: `valkey-primary.valkey.svc.cluster.local`
- **Port**: `6379`
- **Password**: ExternalSecret `valkey-auth` from Vault
  `kv/k8s/valkey/valkey-auth`

**Configuration**:

- No `maxmemory` cap; eviction policy `noeviction` (load-bearing: BullMQ
  queues and OneTimeSecret state must never be silently evicted)
- Persistence: AOF (`appendonly yes`, `save ""`)
- `FLUSHDB`/`FLUSHALL` disabled via rename-command

**Backups**:

A CronJob (`valkey-primary-backup`, 03:30 nightly) takes an RDB snapshot
over the network (`valkey-cli --rdb`) to the dedicated 5Gi
`valkey-primary-backups` PVC, keeping the 7 most recent. Trigger manually:

```bash
kubectl -n valkey create job --from=cronjob/valkey-primary-backup backup-manual
```

Restore procedure: [BACKUP-DR.md](BACKUP-DR.md).

---

## Shared Infrastructure

### PostgreSQL Pattern

**Central PostgreSQL cluster** serves multiple applications:

1. **Deploy PostgreSQL** via the custom homelab chart (official image)
2. **Create databases** with the chart's PostSync hook (`databases:` list)
3. **Apps connect** to `postgresql.postgresql.svc.cluster.local`

**Advantages**:

- ✅ Single database cluster to manage
- ✅ Resource efficiency (shared memory/CPU)
- ✅ Simplified backups
- ✅ Centralized administration

**How to Add a Database**:

1. Store `username`, `password` and `database` in Vault,
   `kv/k8s/postgresql/<app>-db-secret`, and add an ExternalSecret for it in
   `apps/data/postgresql/secrets/` (copy an existing one)
2. Add `- secretName: <app>-db-secret` to `databases:` in
   `apps/data/postgresql/values.yaml`
3. Sync the postgresql application; its hook creates the role and database.
   Check the run:

   ```bash
   kubectl -n postgresql logs job/postgresql-databases
   ```

---

### Valkey (Redis) Pattern

**Shared Valkey instance** provides caching/storage for:

- **SearXNG** - Search result caching, rate limiting
- **Docmost** - Queues and collaboration state
- **OneTimeSecret** - Primary data store (all secret state)

**Connection Pattern** (DSN with a per-app logical database index):

```text
redis://:<password>@valkey-primary.valkey.svc.cluster.local:6379/<db>
```

Claim the next free database index (check the Valkey consumer list above
and the app's Vault entry, `REDIS_URL` in
`kv/k8s/onetimesecret/onetimesecret-secret` for example, and verify with
`valkey-cli -n <db> dbsize` before assuming a slot is free), then store the
DSN in the app's Vault entry.

**Future Consumers**: Any app needing session storage, caching, or rate limiting

---

## Adding a New Application

### Step-by-Step Guide

#### Step 1: Create Directory Structure

Pick the tier the app belongs to (`infra`, `data`, `services`, or `user`):

```bash
mkdir -p apps/<tier>/myapp/{ingress,secrets}
cd apps/<tier>/myapp
```

---

#### Step 2: Create Kustomization.yaml

For **Helm-based app** (custom OCI chart):

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: myapp
helmCharts:
  - name: myapp
    repo: oci://registry.example.com/example-org/helm-charts
    version: 1.0.0
    releaseName: myapp
    namespace: myapp
    valuesFile: values.yaml
resources:
  - ingress/ingressroute.yaml
  - secrets/myapp-secret-external-secret.yaml
```

For **manifest-based app** (raw Kubernetes YAML):

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: myapp
resources:
  - base
  - ingress/ingressroute.yaml
  - secrets/myapp-secret-external-secret.yaml
```

---

#### Step 3: Create config.yaml (REQUIRED)

This file is what the ApplicationSet's files generator
(`apps/*/*/config.yaml`) keys on. **Without it, no Application is generated**,
so the app will neither sync nor be pruned. It declares the app's
per-Application metadata:

```text
---
# Application metadata consumed by argocd/apps-set.yaml (git files generator).
namespace: myapp        # omit → cluster-scoped; otherwise the app's namespace
syncWave: "6"           # string; user tier = 6 (see ARCHITECTURE.md bands)
createNamespace: true   # adds CreateNamespace=true syncOption
# autoSync: true        # layers automated{prune,selfHeal} on top (default: manual)
# serverSideApply: true # adds ServerSideApply=true syncOption
# ignoreDifferences:    # raw passthrough block (e.g. Harbor TLS cert drift)
#   - kind: Secret
#     name: myapp-tls
#     jsonPointers:
#       - /data/tls.crt
```

If `namespace` is omitted, the Application has no destination namespace and is
treated as cluster-scoped. The Application **name** is always the directory
basename (`myapp`), independent of tier.

---

**Step 4: Create values.yaml** (Helm apps)

Create `values.yaml` with Helm chart overrides:

```text
image:
  repository: myapp/myapp
  tag: "1.0.0"

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 128Mi

persistence:
  enabled: true
  storageClass: longhorn
  size: 5Gi

priorityClassName: normal-priority
```

---

#### Step 5: Create IngressRoute

Create `ingress/ingressroute.yaml`. Every app gets a route on the `lan`
entrypoint for `<app>.example.com`, with no SSO middleware; see
[Exposure Model](SECURITY.md#exposure-model) before making anything public:

```text
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: myapp-ingressroute
  namespace: myapp
spec:
  entryPoints:
    - lan
  routes:
    - match: Host(`myapp.example.com`)
      kind: Rule
      services:
        - name: myapp
          port: 80
```

The app's `kustomization.yaml` lists it as `ingress/ingressroute.yaml`;
`ingress/` holds no `kustomization.yaml` of its own.

---

**Step 6: Add Secrets** (if needed)

Write the values into Vault, reading each from stdin:

```bash
vault kv put -mount=kv k8s/myapp/myapp-secret username=- password=-
```

Then add `secrets/myapp-secret-external-secret.yaml`:

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: myapp-secret
  namespace: myapp
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: vault
  target:
    name: myapp-secret
    creationPolicy: Owner
  dataFrom:
    - extract:
        key: k8s/myapp/myapp-secret
```

Shared values (database, Valkey) and rendered DSNs: see
[SECURITY.md](SECURITY.md#adding-a-secret).

---

#### Step 7: Test Locally

```bash
# Validate Kustomize build
kubectl apply -k apps/<tier>/myapp --dry-run=client

# Validate against cluster
kubectl apply -k apps/<tier>/myapp --dry-run=server

# Check for errors
kubectl kustomize apps/<tier>/myapp
```

---

#### Step 8: Commit and Push

```bash
git add apps/<tier>/myapp/
git commit -m "feat(apps): add myapp application"
git push origin main
```

**Outcome**: CI/CD pipeline validates configuration automatically

---

#### Step 9: Sync in ArgoCD

Once the new `config.yaml` is on `main`, the ApplicationSet generates the
`myapp` Application after the next poll (3 minutes).

**Manual sync**:

1. Open ArgoCD UI: `https://argo.example.com`
2. Find `apps` ApplicationSet → Refresh
3. Find new `myapp` Application
4. Click **Sync** → **Synchronize**

---

#### Step 10: Verify Deployment

```bash
# Check application status
kubectl get application myapp -n argocd

# Check pods
kubectl get pods -n myapp

# Check ingress
kubectl get ingressroute -n myapp

# Test URL
curl -k https://myapp.example.com
```

---

### Optional: Publish with SSO Protection

Only `public` routes are gated. To publish an app, add a second IngressRoute
for the same host `myapp.example.com` on `public`, add it as a Cloudflare
tunnel public hostname, and gate it. Gating takes four pieces, all in Git and
order-safe. In the Authentik blueprints, add a proxy provider + application +
`admins` binding (`apps/infra/authentik/blueprints/10-proxy-providers.yaml`) and
list the provider on the embedded outpost (`blueprints/30-outpost.yaml`) — a
host with no application returns 404 from the outpost instead of a login page.
Then reference the `authentik-forwardauth` middleware and add the
middleware-free outpost route on the app's IngressRoute:

```text
spec:
  entryPoints:
    - public
  routes:
    - match: Host(`myapp.example.com`)
      kind: Rule
      middlewares:
        - name: authentik-forwardauth
          namespace: authentik
      services:
        - name: myapp
          port: 80
    - match: Host(`myapp.example.com`) && PathPrefix(`/outpost.goauthentik.io/`)
      kind: Rule
      services:
        - kind: Service
          name: authentik-server
          namespace: authentik
          port: 80
```

See [security.md](SECURITY.md#protecting-an-application-with-sso) for details.

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - GitOps patterns and app-of-apps
- [SECURITY.md](SECURITY.md) - Secret management with Vault and ESO
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md) - Infrastructure components
- [CI-CD-PIPELINE.md](CI-CD-PIPELINE.md) - Validation pipeline
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
