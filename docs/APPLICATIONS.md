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
- 🔐 **SealedSecrets** for credentials (via Kryptos)
- 💾 **Longhorn storage** for persistent data
- 🏷️ **Priority classes** for resource scheduling

## Active Applications

<!-- markdownlint-disable MD013 MD060 -->
| Application            | Description                  | Chart Source  | Version  | Ingress | Secrets |
| ---------------------- | ---------------------------- | ------------- | -------- | ------- | ------- |
| **DocuSeal**           | Document signing platform    | Custom OCI    | 1.0.8    | ✅      | ✅      |
| **Harbor**             | OCI registry                 | Public Helm   | 1.19.2   | ✅      | ✅      |
| **Headlamp**           | Kubernetes management UI     | Public Helm   | 0.44.0   | ✅      | ✅      |
| **Joplin**             | Note-taking server           | Custom OCI    | 1.0.0    | ✅      | ✅      |
| **LiteLLM**            | LLM proxy / gateway          | Custom OCI    | 1.0.6    | ✅      | ✅      |
| **Memos**              | Quick-note memos             | Custom OCI    | 1.0.2    | ✅      | ✅      |
| **OneTimeSecret**      | View-once secret links       | Custom OCI    | 1.0.2    | ✅      | ✅      |
| **Open WebUI**         | LLM chat front-end           | Custom OCI    | 1.0.2    | ✅      | ✅      |
| **PostgreSQL**         | Shared database cluster      | Custom OCI    | 1.0.0    | ❌      | ✅      |
| **PrivateBin**         | Encrypted pastebin           | Custom OCI    | 1.0.1    | ✅      | ❌      |
| **SearXNG**            | Privacy-focused metasearch   | Custom OCI    | 1.1.2    | ✅      | ✅      |
| **SnapOtter**          | File processing platform     | Custom OCI    | 1.0.1    | ✅      | ✅      |
| **Stirling-PDF**       | Self-hosted PDF toolset      | Custom OCI    | 1.0.9    | ✅      | ❌      |
| **Valkey**             | Redis-compatible cache       | Custom OCI    | 1.0.0    | ❌      | ✅      |
<!-- markdownlint-enable MD013 MD060 -->

**Chart Sources**:

- **Custom OCI**: `oci://registry.example.com/example-org/helm-charts` - Custom
  charts from [helm-charts](https://source.example.com/example-org/helm-charts.git)
- **Public Helm**: Standard upstream repositories

## Application Details

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

**Credentials**: SealedSecret for database credentials (Kryptos)

---

### Harbor

**Description**: OCI registry for container images and Helm charts

**Location**: `apps/services/harbor/`

**Chart**: `https://helm.goharbor.io/harbor`
(version pinned in the app kustomization)

**URL**: `https://registry.example.com` (also `registry.example.com`)

**Database**: PostgreSQL (shared cluster); Redis is the chart-bundled
internal instance, not the shared Valkey

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

### Joplin

**Description**: Self-hosted Joplin Server for note synchronisation

**Purpose**: Secure note-taking and to-do management with end-to-end
encryption sync

**Location**: `apps/user/joplin/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/joplin`
(version pinned in the app kustomization)

**URL**: `https://joplin.example.com`

**Database**: PostgreSQL (shared cluster)

**Features**:

- End-to-end encrypted synchronisation
- Multi-device sync via Joplin Server
- Markdown-based notes and to-dos
- REST API for integrations

**Configuration**:

- PostgreSQL database: `joplin` on shared cluster
- Health probes: `/api/ping` endpoint
- Host header validation against `APP_BASE_URL`

---

### LiteLLM

**Description**: LLM proxy / gateway exposing a unified OpenAI-compatible API

**Purpose**: Central gateway for routing requests to multiple LLM providers

**Location**: `apps/user/litellm/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/litellm`
(version pinned in the app kustomization)

**URL**: `https://litellm.example.com`

**Database**: PostgreSQL (shared cluster)

**Features**:

- OpenAI-compatible proxy API
- Multi-provider routing
- Usage tracking in PostgreSQL

**Configuration**:

- PostgreSQL database: `litellm` on shared cluster

**Credentials**: SealedSecret for master key and database credentials (Kryptos)

---

### Memos

**Description**: Quick-note / memo-taking service

**Location**: `apps/user/memos/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/memos`
(version pinned in the app kustomization)

**URL**: `https://memos.example.com`

**Database**: PostgreSQL (shared cluster)

**Credentials**: SealedSecret for database credentials (Kryptos)

---

### OneTimeSecret

**Description**: Expiring, view-once secret links

**Location**: `apps/user/onetimesecret/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/onetimesecret`
(version pinned in the app kustomization)

**URL**: `https://secret.example.com`

**Cache**: Valkey (shared cluster) holds all state

**Credentials**: SealedSecret for encryption key and Valkey URL (Kryptos)

---

### Open WebUI

**Description**: Web front-end for chatting with LLMs

**Purpose**: User-facing chat interface, typically backed by LiteLLM

**Location**: `apps/user/open-webui/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/open-webui`
(version pinned in the app kustomization)

**URL**: `https://open-webui.example.com`

**Features**:

- Conversational chat UI
- Connects to OpenAI-compatible backends (e.g. LiteLLM)

**Authentication**: Built-in login; the tunnel host `chat.example.com`
additionally carries the `authentik-forwardauth` Traefik middleware
(defence in depth)

**Storage**: Persistent data via Longhorn PVC

**Credentials**: SealedSecret for configuration (Kryptos)

---

### PostgreSQL

**Description**: Shared PostgreSQL 18 database cluster

**Purpose**: Central database for applications (Harbor, DocuSeal,
LiteLLM, Joplin, Memos, SnapOtter, Authentik)

**Location**: `apps/data/postgresql/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/postgresql`
(version pinned in the app kustomization; the chart is also VENDORED at
`apps/data/postgresql/charts/` because its OCI source is the in-cluster
Harbor, which depends on this database — keep the vendored copy in lockstep
with the version pin)

**Features**:

- PostgreSQL 18.x (official `docker.io/library/postgres` image, Debian
  variant, digest-pinned)
- Persistent storage via Longhorn
- Nightly `pg_dumpall` backups (see Backups below)
- Priority class: `high-priority-stateful`

**Database Creation**:

Automated via Kubernetes Jobs in `apps/data/postgresql/jobs/`:

- `authentik-db-create-job.yaml` - Creates `authentik` database
- `docuseal-db-create-job.yaml` - Creates `docuseal` database
- `harbor-db-create-job.yaml` - Creates `harbor` database
- `joplin-db-create-job.yaml` - Creates `joplin` database
- `litellm-db-create-job.yaml` - Creates `litellm` database
- `memos-db-create-job.yaml` - Creates `memos` database
- `snapotter-db-create-job.yaml` - Creates `snapotter` database

**Consumers**:

- **Harbor** (services tier)
- **Authentik** (infrastructure component)
- **DocuSeal** (application)
- **Joplin** (application)
- **LiteLLM** (application)
- **Memos** (application)
- **SnapOtter** (application)

**Connection Details**:

- **Host**: `postgresql.postgresql.svc.cluster.local`
- **Port**: `5432`
- **Superuser**: `postgres` (via SealedSecret)
- **Application users**: Created by database jobs

**Credentials**:

Generated via Kryptos: `kryptos/configs/postgresql.yaml`

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

**Purpose**: Securely share text snippets, code, logs

**Location**: `apps/user/privatebin/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/privatebin`
(version pinned in the app kustomization)

**URL**: `https://paste.example.com`

**Features**:

- Client-side encryption (server never sees plaintext)
- Password protection
- Burn after reading
- Syntax highlighting
- File attachments

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

**Credentials**: SealedSecret for admin access (Kryptos)

---

### SnapOtter

**Description**: Self-hosted file processing platform (images, video,
audio, PDF)

**Location**: `apps/user/snapotter/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/snapotter`
(version pinned in the app kustomization)

**URL**: `https://snapotter.example.com`

**Database**: PostgreSQL (shared cluster); Valkey (shared cluster) as
Redis backend

**Credentials**: SealedSecret for database and Valkey URLs (Kryptos)

---

### Stirling-PDF

**Description**: Self-hosted PDF toolset

**Location**: `apps/user/stirling-pdf/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/stirling-pdf`
(version pinned in the app kustomization)

**URL**: `https://pdf.example.com`

---

### Valkey

**Description**: Redis-compatible in-memory data store (Redis fork by
Linux Foundation)

**Purpose**: Shared cache/data store for applications (SearXNG, SnapOtter,
OneTimeSecret)

**Location**: `apps/data/valkey/`

**Chart**: `oci://registry.example.com/example-org/helm-charts/valkey`
(version pinned in the app kustomization; the chart is VENDORED at
`apps/data/valkey/charts/` because its OCI source is the in-cluster Harbor —
same circular dependency as PostgreSQL)

**Features**:

- Valkey (official `valkey/valkey` image, Debian variant, digest-pinned)
- AOF persistence to Longhorn PVC (RDB auto-save off)
- Nightly RDB snapshot backups (see Backups below)
- Priority class: `high-priority-stateful`

**Consumers** (logical database allocation: 0 free, 1-3 assigned):

- **SearXNG** (db 1) - Search result caching and rate limiting
- **SnapOtter** (db 2) - BullMQ job queues
- **OneTimeSecret** (db 3) - Primary data store (ALL state: links + accounts)

**Connection Details**:

- **Host**: `valkey-primary.valkey.svc.cluster.local`
- **Port**: `6379`
- **Password**: Via SealedSecret (Kryptos, `valkey-auth`)

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
2. **Create databases** via Kubernetes Jobs (`apps/data/postgresql/jobs/`)
3. **Apps connect** to `postgresql.postgresql.svc.cluster.local`

**Advantages**:

- ✅ Single database cluster to manage
- ✅ Resource efficiency (shared memory/CPU)
- ✅ Simplified backups
- ✅ Centralized administration

**How to Add a Database**:

1. Add the `<app>-db-secret` to `kryptos/configs/postgresql.yaml`, seal it,
   and register the sealed file in `apps/data/postgresql/secrets/`
2. Clone an existing job (e.g. `snapotter-db-create-job.yaml`) into
   `apps/data/postgresql/jobs/<app>-db-create-job.yaml`
3. Sync the postgresql application, then apply the job **manually** —
   `jobs/kustomization.yaml` stays `resources: []` on purpose (a Completed
   Job never goes OutOfSync, so ArgoCD would re-create stale ones):

   ```bash
   kubectl apply -f apps/data/postgresql/jobs/<app>-db-create-job.yaml
   ```

---

### Valkey (Redis) Pattern

**Shared Valkey instance** provides caching/storage for:

- **SearXNG** - Search result caching, rate limiting
- **SnapOtter** - Redis backend (queues/cache)
- **OneTimeSecret** - Primary data store (all secret state)

**Connection Pattern** (DSN with a per-app logical database index):

```text
redis://:<password>@valkey-primary.valkey.svc.cluster.local:6379/<db>
```

Claim the next free database index (check `kryptos/configs/onetimesecret.yaml`
and `snapotter.yaml` comments for the current map, and verify with
`valkey-cli -n <db> dbsize` before assuming a slot is free), then seal the
DSN into the app's secret via Kryptos.

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
  - ingress
  - secrets
```

For **manifest-based app** (raw Kubernetes YAML):

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: myapp
resources:
  - base
  - ingress
  - secrets
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

Create `ingress/ingressroute.yaml`:

```text
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: myapp-ingressroute
  namespace: myapp
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`myapp.example.com`)
      kind: Rule
      services:
        - name: myapp
          port: 80
```

Create `ingress/kustomization.yaml`:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ingressroute.yaml
```

---

**Step 6: Generate Secrets** (if needed)

Create Kryptos config at `kryptos/configs/myapp.yaml`:

```text
apiVersion: kryptos.dev/v1
kind: SecretConfig

metadata:
  name: "myapp"
  displayName: "My App"
  namespace: "myapp"

spec:
  secrets:
    - name: myapp-credentials
      displayName: "App Credentials"
      description: "Authentication credentials"
      type: Opaque
      fields:
        - name: username
          prompt: "Admin Username"
          default: "admin"
          required: true

        - name: password
          prompt: "Admin Password"
          generator: strong
          required: true
```

Generate secret:

```bash
kryptos   # released binary, run from the repo root
# Select: My App → App Credentials
```

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

### Optional: Enable SSO Protection

Gating an app takes four pieces, all in Git and order-safe. In the
Authentik blueprints, add a proxy provider + application + `admins` binding
(`apps/infra/authentik/blueprints/10-proxy-providers.yaml`) and list the
provider on the embedded outpost (`blueprints/30-outpost.yaml`) — a host
with no application returns 404 from the outpost instead of a login page.
Then reference the `authentik-forwardauth` middleware and add the
middleware-free outpost route on the app's IngressRoute:

```text
spec:
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
- [SECURITY.md](SECURITY.md) - Secret management with Kryptos
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md) - Infrastructure components
- [CI-CD-PIPELINE.md](CI-CD-PIPELINE.md) - Validation pipeline
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
