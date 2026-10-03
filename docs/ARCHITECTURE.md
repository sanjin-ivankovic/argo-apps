# Architecture

This document provides a comprehensive overview of the ArgoCD-based GitOps
architecture for the homelab Kubernetes cluster.

## Table of Contents

- [Overview](#overview)
- [App-of-Apps Pattern](#app-of-apps-pattern)
- [Sync Wave Ordering](#sync-wave-ordering)
- [Bootstrap Process](#bootstrap-process)
- [Application Patterns](#application-patterns)
- [Priority Class System](#priority-class-system)
- [Naming Conventions](#naming-conventions)
- [Architecture Diagrams](#architecture-diagrams)

## Overview

This repository implements a **declarative, GitOps-driven** Kubernetes
platform using:

- **ArgoCD** for continuous delivery and cluster state management
- **App-of-Apps pattern** for automatic application discovery
- **Sync waves** for controlled deployment ordering
- **Manual sync policy** for deliberate change management

**Key Principle**: Git is the single source of truth. All cluster
state declared here; ArgoCD reconciles to match Git.

## App-of-Apps Pattern

### One ApplicationSet with a Git Files Generator

The core of the architecture is a **single ApplicationSet** at
[argocd/apps-set.yaml](../argocd/apps-set.yaml) that generates **every**
Application — infrastructure and user-facing alike — using a Git **files**
generator keyed on each app's `config.yaml`:

```text
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: apps
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - git:
        repoURL: ssh://git@source.example.com/example-org/argo-apps.git
        revision: main
        files:
          - path: apps/*/*/config.yaml
```

**How It Works**:

1. ArgoCD scans `apps/*/*/config.yaml` (i.e. `apps/<tier>/<app>/config.yaml`)
2. Each `config.yaml` becomes one ArgoCD Application
3. Application name = app directory basename (`{{ .path.basename }}`),
   independent of tier
4. The parsed `config.yaml` is merged into the template params, so its keys
   (`namespace`, `syncWave`, `autoSync`, …) drive each Application's metadata
5. **Tier** (`infra` / `data` / `services` / `user`) is purely a human
   grouping — it does not affect the generated Application

**Critical contract**: With a files generator, **every app directory MUST
contain a `config.yaml`** or no Application is generated for it — meaning it
won't sync **and** won't be pruned. Adding a new app therefore requires
creating its `config.yaml`; the `config.yaml` is the wiring.

**Per-app `config.yaml` keys**:

- `namespace:` — destination namespace; **omit → cluster-scoped**; by
  convention defaults to the directory basename
- `syncWave:` — string sync-wave annotation, e.g. `"2"`
- `autoSync:` — bool; adds an `automated` block (`prune` + `selfHeal`).
  Auto-sync is opt-in per app via this key. Default (absent) = manual sync.
- `createNamespace:` — bool; adds the `CreateNamespace=true` syncOption
- `serverSideApply:` — bool; adds the `ServerSideApply=true` syncOption
- `ignoreDifferences:` — raw passthrough block (e.g. Harbor's TLS cert drift)

**Template Behavior**:

- `goTemplate: true` - Uses Go templates for variable expansion
- `missingkey=error` - Fails fast if a template variable is undefined
- `ApplyOutOfSyncOnly=true` - Only applies resources that are
  out-of-sync (optimization), set on every generated Application
- `CreateNamespace=true` - Added per-app when `createNamespace: true`

### Entry Points

There are two ways to bootstrap the entire platform:

**Option 1: Root Application**
([argocd/root.yaml](../argocd/root.yaml))

```text
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  source:
    path: argocd # root.yaml + apps-set.yaml + kustomization.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
```

**Option 2: Direct Kustomization**
([argocd/kustomization.yaml](../argocd/kustomization.yaml))

```bash
kubectl apply -k argocd
```

Both methods deploy the contents of `argocd/`:

- The root Application (self-managing)
- The single ApplicationSet, which generates all apps from
  `apps/*/*/config.yaml`

## Sync Wave Ordering

Sync waves control the **deployment order** to handle dependencies between
components. Lower wave numbers deploy first.

### Wave Bands

Sync waves are now grouped into **tier bands**, set per-app via the
`syncWave:` key in each `config.yaml`:

<!-- markdownlint-disable MD013 MD060 -->
| Band      | Tier       | Example components / apps                          | Purpose                          |
| --------- | ---------- | -------------------------------------------------- | -------------------------------- |
| **-1..3** | `infra`    | priority-classes (-1), argocd/cert-manager/sealed-secrets (0), metallb/longhorn/metrics-server (1), traefik (2), authentik/cloudflare-ddns/cloudflared/external-services (3) | Platform foundation, in dependency order |
| **4**     | `data`     | postgresql, valkey                                 | Shared data services             |
| **5**     | `services` | harbor, headlamp                                   | Platform services (depend on data) |
| **6**     | `user`     | docuseal, joplin, litellm, memos, onetimesecret, open-webui, privatebin, searxng, snapotter, stirling-pdf | User-facing applications         |
<!-- markdownlint-enable MD013 MD060 -->

**Rationale**:

- **Priority Classes first (-1)** - Ensures proper pod scheduling from the start
- **ArgoCD in wave 0** - Self-manages after initial bootstrap
- **Traefik in wave 2** - Required for ingress before apps deploy
- **Longhorn in wave 1** - Required for persistent storage before stateful apps
- **Data tier in wave 4** - Databases ready before services/apps consume them
- **User apps in wave 6** - Deploy last, once all infrastructure is ready

### Sync Wave Configuration

Each app sets its own wave in its `config.yaml`, which the ApplicationSet
renders into the generated Application's `argocd.argoproj.io/sync-wave`
annotation:

```text
# apps/infra/traefik/config.yaml
namespace: traefik
syncWave: "2"
createNamespace: true
```

There is no central kustomization listing waves — the wave lives next to the
app it orders, and the ApplicationSet (itself at sync-wave `"0"`) fans the
values out across all generated Applications.

## Bootstrap Process

The **bootstrap process** solves a chicken-and-egg problem: ArgoCD needs to
be deployed to manage GitOps, but ArgoCD itself should be managed via GitOps.

### Three-Stage Bootstrap

#### Stage 1: Manual ArgoCD Installation

ArgoCD must be installed manually the first time, since it can't deploy
itself:

```bash
# Apply ArgoCD infrastructure manually
kubectl apply -k apps/infra/argocd
```

This creates:

- ArgoCD namespace
- ArgoCD CRDs (Application, ApplicationSet, etc.)
- ArgoCD controllers and UI

#### Stage 2: Infrastructure Bootstrap

Once ArgoCD is running, bootstrap the rest of infrastructure:

```bash
# Apply the root application (app-of-apps)
kubectl apply -f argocd/root.yaml
```

This creates the Root Application pointing to `argocd/`, which deploys the
single ApplicationSet. The ApplicationSet then generates every Application
from `apps/*/*/config.yaml`:

- Infrastructure components (cert-manager, Traefik, Longhorn, etc.)
- Data, services, and user-facing apps

#### Stage 3: ArgoCD Self-Management

After Stage 2, ArgoCD starts managing itself:

1. The ApplicationSet generates the `argocd` Application from
   `apps/infra/argocd/config.yaml`
2. This ArgoCD Application points to `apps/infra/argocd`
3. ArgoCD now manages its own configuration via GitOps

From this point forward, **all changes** (including ArgoCD upgrades) happen
via Git commit → ArgoCD sync.

### Why Three Stages?

- **Stage 1** - Manual install required (nothing exists yet)
- **Stage 2** - ArgoCD deploys infrastructure (ArgoCD exists but isn't
  self-managed)
- **Stage 3** - ArgoCD self-manages (fully GitOps-driven)

See [argocd/README.md](../argocd/README.md) for
detailed bootstrap procedures.

## Application Patterns

There are **two patterns** for deploying applications:

### Pattern 1: Helm-Based Applications

**Most applications** use this pattern with Kustomize's `helmCharts` feature.

**Directory Structure**:

```text
apps/<tier>/<app>/
├── config.yaml             # ApplicationSet metadata (REQUIRED)
├── kustomization.yaml      # Helm chart + Kustomize resources
├── values.yaml             # Helm values overrides
├── ingress/                # Traefik IngressRoute
│   ├── ingressroute.yaml
│   └── kustomization.yaml
└── secrets/                # SealedSecrets
    ├── <app>-secret.yaml
    └── kustomization.yaml
```

**Example kustomization.yaml**:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: searxng
helmCharts:
  - name: searxng
    repo: oci://registry.example.com/example-org/helm-charts
    version: 1.1.2
    releaseName: searxng
    namespace: searxng
    valuesFile: values.yaml
resources:
  - ingress
  - secrets
```

**Chart Sources**:

- **Custom Charts** (OCI): `oci://registry.example.com/example-org/helm-charts`
  - Examples: cloudflare-ddns, cloudflared, docuseal, joplin, litellm, memos,
    onetimesecret, open-webui, postgresql, privatebin, searxng, snapotter,
    stirling-pdf, valkey
  - postgresql and valkey are additionally vendored in-repo
    (`apps/data/{postgresql,valkey}/charts/`): their OCI source is the
    in-cluster Harbor, which depends on those very data services
- **Public Charts**: Standard Helm repositories
  - Authentik: `https://charts.goauthentik.io`

### Pattern 2: Manifest-Based Applications

**Some applications** use raw Kubernetes manifests without Helm.

**Directory Structure**:

```text
apps/<tier>/<app>/
├── config.yaml             # ApplicationSet metadata (REQUIRED)
├── kustomization.yaml
├── base/                   # Raw K8s manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
├── ingress/                # Traefik IngressRoute
│   └── ingressroute.yaml
└── secrets/                # SealedSecrets
    └── <app>-secret.yaml
```

**Example** (any manifest-based app):

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: myapp
resources:
  - base
  - secrets
```

**When to Use**:

- Upstream doesn't provide Helm charts
- Fine-grained control needed over manifest structure
- Custom resources or operator-based deployments

### Adding a New Application

**Step 1**: Create directory structure (pick the tier: `infra` / `data` /
`services` / `user`)

```bash
mkdir -p apps/<tier>/myapp/{ingress,secrets}
```

**Step 2**: Create `kustomization.yaml` (Helm example)

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

**Step 3**: Create `config.yaml` (REQUIRED — the ApplicationSet keys on it)

```text
---
namespace: myapp      # omit → cluster-scoped
syncWave: "6"         # match the tier band (user = 6)
createNamespace: true
# autoSync: true      # opt into automated prune + selfHeal
```

Without this file, the ApplicationSet generates no Application for the app, so
it neither syncs nor gets pruned.

**Step 4**: Create `values.yaml` with Helm values

**Step 5**: Create IngressRoute in `ingress/ingressroute.yaml`

**Step 6**: Generate secrets using Kryptos (see [SECURITY.md](SECURITY.md))

**Step 7**: Test locally

```bash
kubectl apply -k apps/<tier>/myapp --dry-run=server
```

**Step 8**: Commit and push

```bash
git add apps/<tier>/myapp/
git commit -m "feat: add myapp application"
git push
```

**Step 9**: Manually sync in ArgoCD UI

Once `config.yaml` is on `main`, the ApplicationSet generates the new
Application on its next poll — no ApplicationSet editing required.

## Priority Class System

A **three-tier priority class system** ensures critical infrastructure
survives resource pressure.

### Priority Classes

<!-- markdownlint-disable MD013 MD060 -->
| Priority Class            | Value         | Global Default | Use Case         |
| ------------------------- | ------------- | -------------- | ---------------- |
| `critical-infrastructure` | 1,000,000,000 | No             | Traefik, ArgoCD  |
| `high-priority-stateful`  | 100,000,000   | No             | PostgreSQL, etc. |
| `normal-priority`         | 0             | **Yes**        | Stateless apps   |
<!-- markdownlint-enable MD013 MD060 -->

### Priority Class Configuration

Priority classes are defined in
[priority-classes/](../apps/infra/priority-classes/):

```text
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: critical-infrastructure
value: 1000000000
globalDefault: false
description: "Critical infrastructure components"
```

**Usage in Deployments**:

```text
spec:
  template:
    spec:
      priorityClassName: critical-infrastructure
```

### Eviction Behavior

When the cluster is under resource pressure:

1. **Normal-priority pods evicted first** (stateless apps can restart easily)
2. **High-priority-stateful pods protected** (databases shouldn't lose data)
3. **Critical-infrastructure never evicted** (cluster must remain functional)

**Important**: Priority classes must exist **before** pods are scheduled
(sync wave -1).

## Naming Conventions

### Namespace Convention

**Rule**: The Application **name** is always the directory basename. The
**namespace** defaults to that basename **by convention**, but is set
explicitly via the `namespace:` key in each app's `config.yaml` — and is
freely overridable. Omitting `namespace:` makes the Application cluster-scoped.

The ApplicationSet uses `{{ .path.basename }}` for the Application name, and
reads the namespace from `config.yaml`:

```text
metadata:
  name: "{{ .path.basename }}"   # always the dir basename
spec:
  destination:
    {{- if .namespace }}
    namespace: "{{ .namespace }}"   # from config.yaml; omitted → cluster-scoped
    {{- end }}
```

**Examples** (basename = namespace):

- `apps/user/searxng/` → `searxng` namespace
- `apps/data/postgresql/` → `postgresql` namespace
- `apps/user/litellm/` → `litellm` namespace

**Common overrides** (`namespace:` set to something other than the basename):

- **sealed-secrets** → `kube-system`
- **metallb** → `metallb-system`
- **longhorn** → `longhorn-system`
- **external-services** → `traefik`
- **metrics-server** → `kube-system`
- **priority-classes** → no namespace (cluster-scoped; `namespace:` omitted)

### Application Naming

- **Directory basename** = **Application name** (namespace defaults to it but
  is set in `config.yaml`)
- Use **lowercase with hyphens** (e.g., `open-webui`, `cert-manager`)
- Match upstream naming (e.g., `searxng` not `searx-ng`)

### Helm Release Naming

Helm releases typically match the application name:

```text
helmCharts:
  - name: searxng
    releaseName: searxng # Matches app name
    namespace: searxng # Matches app name
```

### Secret Naming

SealedSecrets follow `<app>-<purpose>` pattern:

- `searxng-config` - Application configuration
- `postgresql-secret` - PostgreSQL admin credentials
- `authentik-secret` - Authentik secret key, DB password, and bootstrap
  credentials
- `cloudflare-api` - Cloudflare API token

See [SECURITY.md](SECURITY.md) for secret management details.

## Architecture Diagrams

### GitOps Flow

```text
graph TB
    A[Developer] -->|1. Git Commit| B[Git Repository]
    B -->|2. ArgoCD Polls| C[ArgoCD Controller]
    C -->|3. Detect Drift| D{State Match?}
    D -->|No| E[ArgoCD Syncs]
    D -->|Yes| F[No Action]
    E -->|4. Apply Manifests| G[Kubernetes Cluster]
    G -->|5. Status Update| C

    style B fill:#4CAF50
    style C fill:#2196F3
    style G fill:#FF9800
```

**Flow**:

1. Developer commits changes to Git repository
2. ArgoCD polls repository every 3 minutes (default)
3. ArgoCD compares Git state vs cluster state
4. If drift detected, ArgoCD syncs (applies manifests to cluster)
5. ArgoCD updates Application status

**Manual Sync**: Auto-sync is intentionally disabled. Syncs require manual
approval via ArgoCD UI.

### Platform Architecture

```text
graph TB
    subgraph "Ingress Layer"
        CF[Cloudflare DNS]
        CFT[Cloudflare Tunnel]
        TRA[Traefik Ingress]
        MLB[MetalLB Load Balancer]
    end

    subgraph "Authentication Layer"
        AK[Authentik<br/>ForwardAuth + OIDC provider]
    end

    subgraph "Application Layer"
        APPS[Applications<br/>SearXNG, Open WebUI, etc.]
        EXT[External Services<br/>Proxmox, UniFi, etc.]
    end

    subgraph "Data Layer"
        PG[PostgreSQL]
        VK[Valkey Redis]
        LH[Longhorn Storage]
    end

    subgraph "Platform Layer"
        AR[ArgoCD GitOps]
        CM[cert-manager TLS]
        SS[Sealed Secrets]
    end

    CF --> CFT
    CFT --> TRA
    TRA --> MLB
    TRA --> AK
    AK --> APPS
    TRA --> EXT
    APPS --> PG
    APPS --> VK
    APPS --> LH
    AR -.Manages.-> APPS
    AR -.Manages.-> TRA
    AR -.Manages.-> AK
    CM -.Provides TLS.-> TRA
    SS -.Encrypts.-> APPS

    style CF fill:#FF6F00
    style AR fill:#F4511E
    style AK fill:#6A1B9A
    style TRA fill:#1976D2
    style LH fill:#388E3C
```

**Layers**:

- **Ingress**: Cloudflare Tunnel → Traefik → MetalLB
- **Authentication**: Authentik — the `authentik-forwardauth` Traefik
  middleware for gated routes, and an OIDC provider for Headlamp, Omni,
  and SnapOtter
- **Applications**: User-facing apps + proxied external services
- **Data**: PostgreSQL, Valkey (Redis), Longhorn (storage)
- **Platform**: ArgoCD (GitOps), cert-manager (TLS), Sealed Secrets

## Auto-Sync Policy

**Auto-sync is intentionally disabled** across all applications.

**Why Manual Sync?**

1. **Deliberate change management** - Every change requires explicit approval
2. **Prevents cascading failures** - Bad manifest doesn't auto-deploy
   to all apps
3. **GitOps hygiene** - Forces review of what's being deployed
4. **Learning/portfolio context** - Demonstrates operational maturity

**How to Sync**:

After pushing changes to Git:

```bash
# Via ArgoCD CLI
argocd app sync <app-name>

# Via ArgoCD UI
https://argo.example.com → Select app → Sync button
```

**Configuration**: The ApplicationSet template defaults to manual sync — the
`automated` block is only rendered when an app sets `autoSync: true` in its
`config.yaml`. Auto-sync is opt-in per app, kept next to the app rather than in
a central allowlist.

```text
# argocd/apps-set.yaml (template excerpt)
syncPolicy:
  {{- if .autoSync }}        # only when config.yaml sets autoSync: true
  automated:
    prune: true
    selfHeal: true
  {{- end }}
  syncOptions:
    - ApplyOutOfSyncOnly=true
    {{- if .createNamespace }}
    - CreateNamespace=true
    {{- end }}
```

## Related Documentation

- [Applications Reference](APPLICATIONS.md) - Catalog of deployed applications
- [Infrastructure Components](INFRASTRUCTURE.md) - Infrastructure layer details
- [Security Architecture](SECURITY.md) - Secrets, SSO, and TLS
- [CI/CD Pipeline](CI-CD-PIPELINE.md) - Validation and testing
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Bootstrap README](../argocd/README.md) - Detailed bootstrap
  procedures
