# Infrastructure

This document provides comprehensive documentation for all infrastructure
components that power the platform.

## Table of Contents

- [Overview](#overview)
- [Infrastructure Components](#infrastructure-components)
- [Component Details](#component-details)
- [External Services](#external-services)
- [Maintenance](#maintenance)

## Overview

The platform's infrastructure components are organized by sync waves for
controlled deployment ordering.

**Deployment Waves**:

- **Wave -1**: Priority Classes (foundational scheduling)
- **Wave 0**: ArgoCD, cert-manager, Sealed Secrets (core platform)
- **Wave 1**: MetalLB, Longhorn, Metrics Server (networking, storage, metrics)
- **Wave 2**: Traefik (ingress controller)
- **Wave 3**: Authentik, Cloudflare DDNS, Cloudflared, External Services

**Location**: `apps/infra/` (infrastructure manifests, one dir per component)

**Management**: Each component ships an `apps/infra/<component>/config.yaml`.
The single ApplicationSet at
[argocd/apps-set.yaml](../argocd/apps-set.yaml) (git files generator,
`path: apps/*/*/config.yaml`) generates one ArgoCD Application per component
from that file — there are no hand-written per-component Application manifests.

## Infrastructure Components

<!-- markdownlint-disable MD013 MD060 -->
| Component             | Namespace         | Source            | Wave | Priority            |
| --------------------- | ----------------- | ----------------- | --------- | ------------------------- |
| **Priority Classes**  | Cluster-wide      | Raw manifests     | -1        | N/A                       |
| **ArgoCD**            | `argocd`          | Kustomize         | 0         | `critical-infrastructure` |
| **cert-manager**      | `cert-manager`    | Jetstack Helm     | 0         | `critical-infrastructure` |
| **Sealed Secrets**    | `kube-system`     | GitHub releases   | 0         | `critical-infrastructure` |
| **MetalLB**           | `metallb-system`  | MetalLB Helm      | 1         | `critical-infrastructure` |
| **Traefik**           | `traefik`         | Traefik Helm      | 2         | `critical-infrastructure` |
| **Longhorn**          | `longhorn-system` | Longhorn Helm     | 1         | `high-priority-stateful`  |
| **Metrics Server**    | `kube-system`     | Metrics Server    | 1         | `critical-infrastructure` |
| **External Services** | `traefik`         | Raw manifests     | 3         | N/A                       |
| **Cloudflare DDNS**   | `cloudflare-ddns` | Custom OCI        | 3         | `normal-priority`         |
| **Cloudflared**       | `cloudflared`     | Custom OCI        | 3         | `normal-priority`         |
| **Authentik**         | `authentik`       | Authentik Helm    | 3        | `high-priority-stateful`  |
<!-- markdownlint-enable MD013 MD060 -->

---

## Component Details

### Priority Classes

**Description**: Three-tier priority class system for pod scheduling

**Location**: `apps/infra/priority-classes/`

**Sync Wave**: -1 (must exist before pods are scheduled)

**Classes**:

<!-- markdownlint-disable MD013 MD060 -->
| Class                     | Value         | Global Default | Use Case                |
| ------------------------- | ------------- | -------------- | ----------------------- |
| `critical-infrastructure` | 1,000,000,000 | No             | Traefik, ArgoCD, etc.   |
| `high-priority-stateful`  | 100,000,000   | No             | Databases, caches       |
| `normal-priority`         | 0             | **Yes**        | Stateless applications  |
<!-- markdownlint-enable MD013 MD060 -->

**Eviction Order**: Under resource pressure, normal-priority pods evicted
first, then high-priority-stateful, critical-infrastructure never evicted.

**Resources**:

- `critical-infrastructure.yaml`
- `high-priority-stateful.yaml`
- `normal-priority.yaml`

---

### ArgoCD

**Description**: GitOps continuous delivery platform

**Location**: `apps/infra/argocd/`

**Namespace**: `argocd`

**Sync Wave**: 0

**Priority Class**: `critical-infrastructure`

**Components**:

- `argocd-server` - Web UI and API
- `argocd-repo-server` - Git repository interface
- `argocd-application-controller` - Reconciliation loop
- `argocd-dex-server` - SSO (optional)
- `argocd-redis` - Cache for application state

**Features**:

- Self-managing via GitOps after bootstrap
- UI: `https://argo.example.com`
- Manual sync policy (auto-sync disabled)
- Git polling: Every 3 minutes
- ApplicationSet for automatic app discovery

**High Availability**: 1 replica (sufficient for homelab)

**Storage**: Persistent volume for repository cache

---

### cert-manager

**Description**: Automated TLS certificate management

**Location**: `apps/infra/cert-manager/`

**Namespace**: `cert-manager`

**Chart**: Jetstack cert-manager with CRDs
(version pinned in the app kustomization)

**Sync Wave**: 0

**Priority Class**: `critical-infrastructure`

**Components**:

- `cert-manager-controller` - Certificate lifecycle management
- `cert-manager-webhook` - Validating webhook for CRDs
- `cert-manager-cainjector` - CA bundle injection

**ClusterIssuers**:

- `letsencrypt-prod` - Production Let's Encrypt
- `letsencrypt-staging` - Staging Let's Encrypt (testing)

**Challenge Method**: DNS01 via Cloudflare

**Wildcard Certificate**: `*.example.com` (auto-renews 30 days before expiry)

**Configuration**:

- DNS01 recursive nameservers: `1.1.1.1`, `1.0.0.1`
- Cloudflare API token: SealedSecret
- Node affinity: Infrastructure tier
- Tolerations: Control-plane taints

See [SECURITY.md](SECURITY.md#tls-certificates) for details.

---

### Sealed Secrets

**Description**: Encrypted secrets controller for GitOps-friendly secret
management

**Location**: `apps/infra/sealed-secrets/`

**Namespace**: `kube-system`

**Source**: GitHub releases (version pinned in the app kustomization)

**Sync Wave**: 0

**Priority Class**: `critical-infrastructure`

**How It Works**:

1. Encrypt secrets locally with `kubeseal` CLI
2. Commit encrypted SealedSecret to Git
3. Controller in cluster decrypts → creates Secret
4. Applications consume decrypted Secret

**Encryption**: RSA 4096-bit key pair (generated on first install)

**Patches**:

- Node affinity for infrastructure tier
- Tolerations for control-plane taints
- Resource limits

**Public Key Retrieval**:

```bash
kubeseal --fetch-cert > pub-cert.pem
```

See [SECURITY.md](SECURITY.md#sealed-secrets) for usage details.

---

### MetalLB

**Description**: Bare metal load balancer (L2 mode)

**Location**: `apps/infra/metallb/`

**Namespace**: `metallb-system`

**Chart**: `https://metallb.github.io/metallb`
(version pinned in the app kustomization)

**Sync Wave**: 1

**Priority Class**: `critical-infrastructure`

**Mode**: Layer 2 (ARP)

**IP Pool Configuration**:

```text
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default
  namespace: metallb-system
spec:
  addresses:
    - 10.10.0.60-10.10.0.70
```

**L2Advertisement**: Announces IPs via ARP on local network

**Assigned IPs** (pinned with the `metallb.io/loadBalancerIPs` annotation):

<!-- markdownlint-disable MD013 -->
| IP | Services | Purpose |
| --- | --- | --- |
| 10.10.0.67 | `traefik/traefik-lan` (443, 80), `traefik/gitlab-ssh-lan` (22) | LAN: `lan`/`lanweb`, GitLab SSH; every LAN DNS name points here; shared via `metallb.io/allow-shared-ip: lan-shared-ip` |
| 10.10.0.68 | `postgresql/postgresql` (5432) | Shared PostgreSQL |
| 10.10.0.69 | `traefik/traefik` (80, 443) | Public: `web`/`websecure`; reached by the Cloudflare tunnel via ClusterIP, no LAN DNS name |
<!-- markdownlint-enable MD013 -->

**Components**:

- `metallb-controller` - IP allocation
- `metallb-speaker` - ARP announcement (DaemonSet)

---

### Traefik

**Description**: Cloud-native edge router and Kubernetes Ingress controller

**Location**: `apps/infra/traefik/`

**Namespace**: `traefik`

**Chart**: Traefik Helm chart (official)

**Sync Wave**: 2

**Priority Class**: `critical-infrastructure`

**Features**:

- HTTP/HTTPS ingress
- IngressRoute CRD (Traefik-native, NOT standard Kubernetes Ingress)
- TLS termination
- ForwardAuth middleware (Authentik integration)
- Let's Encrypt integration via cert-manager
- Automatic HTTP → HTTPS redirect

**EntryPoints**:

<!-- markdownlint-disable MD013 -->
| Entrypoint | Port | Exposed on | Serves |
| --- | --- | --- | --- |
| `web` | 80 | `traefik` (10.10.0.69) | Redirect to `websecure` |
| `websecure` | 443 | `traefik` (10.10.0.69) | Public routes (tunnel origin), gated where needed |
| `lanweb` | 80 | `traefik-lan` (10.10.0.67) | Redirect to `lan` |
| `lan` | 443 | `traefik-lan` (10.10.0.67) | Every app, ungated |
<!-- markdownlint-enable MD013 -->

Each port opts into one Service through the chart's per-port `expose` map, so
the `lan` entrypoint is never reachable through the tunnel. Every app has a
`lan` route; public apps add a `websecure` route for the same host. See
[Exposure Model](SECURITY.md#exposure-model).

**Service Type**: `LoadBalancer` (MetalLB provides external IP)

**Certificates**: one wildcard certificate (`example.com`, `*.example.com`)
served by the default `TLSStore` on every TLS entrypoint

**Middleware**:

- `chain-no-auth` (rate limit + security headers) - applied to `websecure` and
  `lan` at entrypoint level
- `authentik-forwardauth` (in the `authentik` namespace) - SSO authentication
  via Authentik's embedded outpost, on the four gated public hosts

**Important**: Use `IngressRoute` CRD, not `kind: Ingress` (standard K8s
resource).

---

### Longhorn

**Description**: Cloud-native distributed block storage for Kubernetes

**Location**: `apps/infra/longhorn/`

**Namespace**: `longhorn-system`

**Chart**: `https://charts.longhorn.io`
(version pinned in the app kustomization)

**Sync Wave**: 1

**Priority Class**: `high-priority-stateful`

**Features**:

- Distributed replicated storage
- Snapshots and backups
- Storage class provider
- Web UI for management

**Storage Classes**:

- `longhorn` - Default storage class (3 replicas)

**UI**: `https://longhorn.example.com` (LAN-only on the `lan` entrypoint, no
login — Longhorn has no auth of its own, so it must never be routed through
`websecure` or the tunnel)

**Backup Target**: External S3-compatible store (configure your own target
if you need backups)

**Components**:

- `longhorn-manager` - Storage orchestration (DaemonSet)
- `longhorn-driver` - CSI driver
- `longhorn-ui` - Web interface

**Node Requirements**:

- `open-iscsi` package installed
- `multipathd` configured (blacklist virtual disks)

**Troubleshooting**: See
[TROUBLESHOOTING.md](TROUBLESHOOTING.md#longhorn--multipathd-issues-ubuntu-2404)

---

### External Services

**Description**: Proxying external services (non-Kubernetes apps) via Traefik

**Location**: `apps/infra/external-services/`

**Namespace**: `traefik`

**Sync Wave**: 3

**Purpose**: Route hosts that run outside the cluster (Proxmox LXCs, Unraid)
through Traefik with the shared wildcard certificate. "External" means
off-cluster backend, not internet-facing: only `translate`, `plex` and `seerr`
also have a `websecure` route.

**Pattern**: selectorless headless Service → EndpointSlice (backend IP:port)
→ IngressRoute

**Services Proxied** (27 hostnames across 13 IngressRoute manifests in
`apps/infra/external-services/ingress-routes/`):

<!-- markdownlint-disable MD013 MD060 -->
| Manifest | Hosts |
| --- | --- |
| **bitwarden** | `bitwarden.example.com`, `smtp4dev.example.com` |
| **gitlab** | `source.example.com` (SSH: `gitlab-ssh-lan` on 10.10.0.67) |
| **immich** | `immich.example.com` |
| **komodo** | `komodo.example.com` |
| **libretranslate** | `translate.example.com` (public, ForwardAuth), `translate.example.com` (LAN, ungated) |
| **nextcloud** | `nextcloud.example.com` |
| **paperless-ngx** | `paperless.example.com` |
| **pihole** | `pihole1.example.com`, `pihole2.example.com` |
| **semaphore** | `semaphore.example.com` |
| **servarr** | `bazarr`, `lingarr`, `notifiarr`, `prowlarr`, `qbit`, `radarr`, `sonarr` (LAN only); `plex`, `seerr` (LAN + public) |
| **technitium** | `dns1.example.com`, `dns2.example.com` |
| **unraid** | `unraid.example.com` |
| **zerobyte** | `zerobyte.example.com` |
<!-- markdownlint-enable MD013 MD060 -->

**Example Configuration** (Unraid,
`apps/infra/external-services/`):

```text
# Service (selectorless, headless)
apiVersion: v1
kind: Service
metadata:
  name: unraid
  namespace: traefik
spec:
  clusterIP: None
  ports:
    - port: 80
      targetPort: 80
      name: http
      protocol: TCP

# EndpointSlice (backend IP mapping)
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: unraid
  namespace: traefik
  labels:
    kubernetes.io/service-name: unraid
addressType: IPv4
endpoints:
  - addresses:
      - 10.30.0.30
    conditions:
      ready: true
ports:
  - port: 80
    name: http
    protocol: TCP

# IngressRoute
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: unraid-ingressroute
  namespace: traefik
spec:
  entryPoints:
    - lan
  routes:
    - kind: Rule
      match: Host(`unraid.example.com`)
      services:
        - kind: Service
          name: unraid
          port: 80
          scheme: http
```

---

### Cloudflare DDNS

**Description**: Keeps Cloudflare DNS records pointed at the current public
IP (replaces the UniFi OS built-in DDNS client)

**Location**: `apps/infra/cloudflare-ddns/`

**Namespace**: `cloudflare-ddns`

**Chart**: `oci://registry.example.com/example-org/helm-charts/cloudflare-ddns`
(version pinned in the app kustomization)

**Sync Wave**: 3

**Priority Class**: `normal-priority`

**Credentials**: Cloudflare API token via SealedSecret (Kryptos)

---

### Cloudflared

**Description**: Cloudflare Tunnel for secure external access without
exposing ports

**Location**: `apps/infra/cloudflared/`

**Namespace**: `cloudflared`

**Chart**: `oci://registry.example.com/example-org/helm-charts/cloudflared`
(version pinned in the app kustomization)

**Sync Wave**: 3

**Priority Class**: `normal-priority`

**Purpose**: Create secure tunnel from Cloudflare edge to cluster

**Configuration**:

- Tunnel token: SealedSecret (generated via Kryptos)
- Tunnel name: `homelab-k8s`
- Ingress rules route each public hostname → Traefik `websecure`
  (ClusterIP); the `lan` entrypoint is not an origin

**Features**:

- No inbound firewall holes
- DDoS protection via Cloudflare
- Automatic TLS termination
- Zero Trust access policies

**Publicly exposed apps**: Only hostnames added as tunnel **public hostnames**
(in the Cloudflare Zero Trust dashboard) are reachable externally, and only
through their `websecure` route; LAN-only apps have no public DNS and no tunnel
route. Each public hostname points at Traefik's `websecure`, so the gated
per-app IngressRoute (and any SSO middleware) applies. The full list with gates
is in [SECURITY.md](SECURITY.md#what-the-tunnel-actually-publishes); highlights:

- `privatebin.example.com` — Authentik SSO (PrivateBin has no auth of its own)
- `chat.example.com` — Open WebUI, Authentik SSO **in addition to** Open
  WebUI's built-in login on the tunnel; the `lan` route for the same host
  keeps the built-in login alone.
- `auth.example.com` — the Authentik portal itself; it must stay published so
  the login redirects of gated tunnel hosts can complete externally.

**Credentials**: Generated via Kryptos
(`kryptos/configs/cloudflared.yaml`)

---

### Authentik

**Description**: SSO portal, Traefik ForwardAuth provider (embedded
outpost), **and OIDC provider** — the single identity component for the
platform. Every ForwardAuth-gated route runs on Authentik, and Headlamp,
SnapOtter, Domain Watchdog, HedgeDoc, Stirling-PDF, and Semaphore
authenticate against its OIDC
clients.

**Location**: `apps/infra/authentik/`

**Namespace**: `authentik`

**Chart**: `https://charts.goauthentik.io/authentik`
(version pinned in the app kustomization)

**Sync Wave**: 3 — Authentik depends on PostgreSQL (wave 4), so on a cold
bootstrap it crash-loops until the database is up, then recovers on its own.
The inversion is intentional; the infra band caps at 3.

**Priority Class**: `high-priority-stateful`

**Workloads**: `authentik-server` (portal, API, embedded outpost) and
`authentik-worker` (background tasks, blueprint application) Deployments.

**UI**: `https://auth.example.com` — Traefik IngressRoute → Service
`authentik-server` port 80 → container 9000, wildcard `*.example.com` cert
from the default TLSStore. The portal route carries **no** auth middleware:
Authentik is the auth source, so gating it is a login loop.

**Features**:

- Single ForwardAuth middleware (`authentik-forwardauth`) backed by the
  embedded outpost at `/outpost.goauthentik.io/auth/traefik`
- Per-app proxy providers in `forward_single` mode; access control is a
  per-application `admins` group binding — a host with no application gets
  a 404 from the outpost (fails closed), a user outside `admins` is denied
- Declarative blueprints for providers, applications, bindings, and the
  outpost assignment; flows, users, and MFA enrolment are UI-managed

**Database**: `authentik` database on the shared PostgreSQL cluster, created
by the manual job `apps/data/postgresql/jobs/authentik-db-create-job.yaml`.
PostgreSQL is the **only** backend — Authentik uses no Redis/Valkey.

**Credentials**: Generated via Kryptos
([kryptos/configs/authentik.yaml](../kryptos/configs/authentik.yaml)) and
stored as SealedSecrets in `apps/infra/authentik/secrets/`:

- `authentik-secret` — `AUTHENTIK_SECRET_KEY` (**immutable**: cookie signing
  and unique IDs), `AUTHENTIK_POSTGRESQL__PASSWORD` (derived from the
  postgresql `authentik-db-secret`), and `AUTHENTIK_BOOTSTRAP_PASSWORD` /
  `AUTHENTIK_BOOTSTRAP_TOKEN` (first-boot credentials for `akadmin`, the
  break-glass admin)
- `authentik-oidc-clients` — plaintext OIDC client secrets (single source of
  truth), read by the blueprints via `!Env` from the worker environment

**Notifications**: No SMTP relay in the cluster — password recovery links
are minted in the Admin UI (user → *View recovery link*).

**Blueprints (config-as-code)**: `apps/infra/authentik/blueprints/*.yaml`,
mounted into the worker via the `authentik-blueprints` ConfigMap (kustomize
`configMapGenerator`, chart value `blueprints.configMaps`):

- `00-groups.yaml` — group `admins`
- `10-proxy-providers.yaml` — 7 forward-auth proxy providers with their
  applications and admins-only bindings
- `20-oauth2-providers.yaml` — 6 OIDC providers + scope mappings
- `30-outpost.yaml` — embedded outpost provider assignment

**Traefik Middleware**:

```text
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: authentik-forwardauth
  namespace: authentik
spec:
  forwardAuth:
    address: http://authentik-server.authentik.svc.cluster.local/outpost.goauthentik.io/auth/traefik
    trustForwardHeader: true
    maxResponseBodySize: 1048576
    authResponseHeaders:
      - X-authentik-username
      - X-authentik-groups
      - X-authentik-email
      - X-authentik-name
      - X-authentik-uid
```

**Chart caveat**: chart versions track authentik releases (`YYYY.M.patch`)
and the values contract moves between minors (2025.10 removed Redis
entirely). Pin the exact version and re-render before accepting a Renovate
bump.

#### Validating an Authentik config change before syncing

There is no offline config validator. `kustomize build apps/infra/authentik
--enable-helm` proves the manifests render; whether Authentik accepts a
blueprint only shows up **after sync**, on the blueprint instance status:
Admin UI → Customization → Blueprints (or the worker logs). A failed
blueprint shows "error" on the instance — the pods do not crash. On the
first parallel apply, instances can transiently show "error" from cross-file
ordering; re-applying clears it.

---

## External Services Overview

See [External Services](#external-services) in Component Details above for
the full list of 14 proxied off-cluster manifests.

**Purpose**: Serve every homelab service — in-cluster or not — through the
same Traefik, wildcard certificate and two-tier naming
(`<app>.example.com`, public only where a `websecure` route exists).

**Benefits**:

- ✅ Single wildcard certificate
- ✅ Centralized access logs
- ✅ Public routes gated at the edge (Cloudflare Access, Authentik ForwardAuth)
- ✅ No inbound port exposure (Cloudflare Tunnel)

---

## Maintenance

### Upgrading Infrastructure Components

**Process**:

1. **Update chart version** in
   `apps/infra/<component>/kustomization.yaml`
2. **Update values** in `apps/infra/<component>/values.yaml`
   if needed
3. **Test locally**:

   ```bash
   kubectl apply -k apps/infra/<component> --dry-run=server
   ```

4. **Commit and push**:

   ```bash
   git add apps/infra/<component>/
   git commit -m "chore(infra): upgrade <component> to vX.Y.Z"
   git push
   ```

5. **Manually sync** in ArgoCD UI

**Important**: Sync waves ensure proper ordering during upgrades.

---

### Adding New Infrastructure Component

Infrastructure components follow the **same unified contract** as every other
app: a directory under `apps/infra/` plus a `config.yaml`. There are no
hand-written ArgoCD `Application` manifests to maintain — the ApplicationSet
generates the Application from `config.yaml`.

**Step 1**: Create directory structure

```bash
mkdir -p apps/infra/mycomponent
```

**Step 2**: Create the component configuration in
`apps/infra/mycomponent/` (Helm `kustomization.yaml` + `values.yaml`, or raw
manifests — same as any app).

**Step 3**: Create `apps/infra/mycomponent/config.yaml` declaring the
Application metadata the ApplicationSet consumes:

```text
---
# Application metadata consumed by argocd/apps-set.yaml (git files generator).
namespace: mycomponent   # omit → cluster-scoped (e.g. priority-classes)
syncWave: "3"            # infra band is -1..3 (see ARCHITECTURE.md)
createNamespace: true    # adds CreateNamespace=true syncOption
# serverSideApply: true  # adds ServerSideApply=true syncOption
# autoSync: true         # layers automated{prune,selfHeal} on top
# ignoreDifferences: [...] # raw passthrough block
```

**Without `config.yaml` the ApplicationSet will not generate an Application**,
so the component will neither sync nor be pruned.

**Step 4**: Test locally

```bash
kubectl apply -k apps/infra/mycomponent --dry-run=server
```

**Step 5**: Commit, push, then refresh the `apps` ApplicationSet and sync the
new `mycomponent` Application in ArgoCD.

---

### Backup and Disaster Recovery

**GitOps Benefits**:

- ✅ **Git is the backup** - All configuration in version control
- ✅ **Declarative recovery** - Re-apply `argocd/` (root Application +
  ApplicationSet) to rebuild the entire platform
- ✅ **State versioning** - Git history = infrastructure change log

**Sealed Secrets Backup**:

- Backup sealed-secrets controller private key:

  ```bash
  kubectl get secret -n kube-system sealed-secrets-key -o yaml > sealed-secrets-key.yaml
  ```

- Store securely (offline backup, password manager, etc.)
- Restore key before deploying SealedSecrets

**Persistent Data Backup**:

- PostgreSQL: nightly `pg_dumpall` CronJob to the `postgresql-backups` PVC
  (retention 7; see [BACKUP-DR.md](BACKUP-DR.md))
- Longhorn volumes: no snapshot/backup schedule is configured — the
  Postgres dumps are currently the only automated data backup

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - GitOps patterns and sync waves
- [SECURITY.md](SECURITY.md) - TLS, SSO, secrets management
- [APPLICATIONS.md](APPLICATIONS.md) - User-facing applications
- [CI-CD-PIPELINE.md](CI-CD-PIPELINE.md) - Validation pipeline
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- [argocd/README.md](../argocd/README.md) -
  Bootstrap process
