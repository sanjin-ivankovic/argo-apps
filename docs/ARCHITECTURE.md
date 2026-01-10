# Architecture Documentation

## Table of Contents

- [Overview](#overview)
- [GitOps Architecture](#gitops-architecture)
- [App-of-Apps Pattern](#app-of-apps-pattern)
- [Repository Structure](#repository-structure)
- [Application Architecture](#application-architecture)
- [Infrastructure Architecture](#infrastructure-architecture)
- [Network Architecture](#network-architecture)
- [Storage Architecture](#storage-architecture)
- [Security Architecture](#security-architecture)
- [Data Flow & Dependencies](#data-flow--dependencies)
- [Design Decisions](#design-decisions)
- [Related Documentation](#related-documentation)

---

## Overview

This repository implements a **GitOps-based Kubernetes homelab** using
ArgoCD's App-of-Apps pattern. All infrastructure and applications are
managed declaratively through Git, providing version control, audit
trails, and automated deployment capabilities.

### Key Principles

1. **Git as Single Source of Truth**: All configuration is stored in Git
2. **Declarative Configuration**: Infrastructure and applications defined
   as code
3. **Separation of Concerns**: Platform components vs. application workloads
4. **Categorization**: Applications organized by purpose and criticality
5. **Manual Sync Control**: Intentional manual sync for safety and control

### Architecture Layers

```text
┌─────────────────────────────────────────────────────────┐
│              Management Layer (ArgoCD)                  │
│  ┌───────────────────────────────────────────────────┐  │
│  │         App-of-Apps (Parent Application)          │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼─────┐
│ Platform     │ │ Application │ │ External   │
│ Components   │ │ Workloads   │ │ Services   │
└──────────────┘ └─────────────┘ └────────────┘
```

---

## GitOps Architecture

### Core Concepts

**GitOps** is an operational framework that uses Git as the single source
of truth for declarative infrastructure and applications. This repository
implements GitOps principles:

- **Version Control**: All changes tracked in Git
- **Pull-Based Model**: ArgoCD pulls from Git repository
- **Declarative**: Desired state defined in YAML manifests
- **Automated**: ArgoCD continuously reconciles cluster state with Git
- **Auditable**: Complete history of all changes

### GitOps Workflow

```text
Developer → Git Commit → Git Push → ArgoCD Detects Change → Sync to Cluster
```

1. **Developer makes changes** to manifests in Git
2. **Changes committed and pushed** to `main` branch
3. **ArgoCD detects changes** via polling or webhook
4. **Manual sync triggered** (auto-sync disabled for safety)
5. **ArgoCD applies changes** to Kubernetes cluster
6. **Status reported** back to ArgoCD UI

### Repository Configuration

- **Repository URL**: `ssh://git@gitlab.example.com:2424/homelab/argo-apps.git`
- **Branch**: `main` (production)
- **Path Structure**: Organized by platform vs. applications
- **Sync Policy**: Manual sync (intentional for control)

---

## App-of-Apps Pattern

### Pattern Description

The **App-of-Apps pattern** is an ArgoCD best practice that uses a parent
application to manage multiple child applications. This provides:

- **Centralized Management**: Single entry point for all deployments
- **Consistent Configuration**: Shared sync policies and settings
- **Dependency Management**: Control deployment order
- **Scalability**: Easy to add/remove applications

### Hierarchy

```text
app-of-apps (Parent)
├── argocd (Self-management)
├── traefik (Ingress)
├── cert-manager (Certificates)
├── metallb (Load Balancer)
├── longhorn (Storage)
├── monitoring (Prometheus/Grafana) [planned/inactive]
├── external-services (Service Proxies)
└── apps-set (ApplicationSet)
    ├── affine
    ├── postgresql
    ├── valkey
    ├── home-assistant
    ├── it-tools
    └── ... (all other apps)
```

### Parent Application

**File**: `argocd/app-of-apps.yaml`

```text
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: app-of-apps
  namespace: argocd
spec:
  source:
    repoURL: https://gitlab.example.com/homelab/argo-apps.git
    targetRevision: main
    path: argocd # Points to ArgoCD applications
```

**Key Points**:

- Entry point for entire stack
- Deploys all applications from `argocd/` directory
- Manually applied: `kubectl apply -f bootstrap/root.yaml` or `kubectl apply
-k argocd/`

### ArgoCD Applications

Located in `argocd/`:

1. **Infrastructure Applications** (`argocd/infrastructure/`):
   - `argocd.yaml` - ArgoCD self-management
   - `traefik.yaml` - Ingress controller
   - `cert-manager.yaml` - Certificate management
   - `metallb.yaml` - Load balancer
   - `longhorn.yaml` - Storage
   - `monitoring.yaml` - Monitoring stack
   - `cloudflared.yaml` - Cloudflare tunnel
   - `external-services.yaml` - External service proxies

2. **Application Workloads** (`argocd/applications/`):
   - `apps-set.yaml` - ApplicationSet managing all apps via Git directory
     generator

### ApplicationSet Pattern

**File**: `argocd/applications/apps-set.yaml`

Uses ArgoCD ApplicationSet with a **Git directory generator** to
automatically discover all application workloads:

```text
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
spec:
  generators:
    - git:
        repoURL: https://gitlab.example.com/homelab/argo-apps.git
        revision: main
        directories:
          - path: apps/*
        # Auto-discovers all apps in apps/ directory
        # Namespace automatically set to app name
```

**Benefits**:

- Single file manages all apps
- Easy to add/remove apps
- Consistent configuration across apps
- Template-based generation

### Sync Policy

**Important**: Automated sync is **intentionally disabled** across all
applications.

```text
syncPolicy:
  # automated:  # Commented out for manual control
  #   prune: true
  #   selfHeal: true
  syncOptions:
    - ApplyOutOfSyncOnly=true
```

**Rationale**:

- **Safety**: Prevents accidental deployments
- **Control**: Manual review before applying changes
- **Stability**: Reduces risk of automatic reconciliation loops
- **Audit**: Explicit sync actions in ArgoCD UI

**Sync Workflow**:

1. Make changes in Git
2. Commit and push to `main`
3. ArgoCD detects drift
4. Manually sync via ArgoCD UI or CLI
5. Monitor sync status

---

## Repository Structure

### Directory Organization

```text
argo-apps/
├── argocd/                   # ArgoCD bootstrap layer
│   ├── kustomization.yaml    # Root kustomization (app-of-apps)
│   ├── infrastructure/       # Infrastructure Application manifests
│   └── applications/         # Application ApplicationSet
│       └── apps-set.yaml     # Git directory generator for apps/*
├── infrastructure/           # Infrastructure components
│   ├── argocd/               # ArgoCD configuration
│   ├── cert-manager/         # Cert-Manager
│   ├── cloudflared/          # Cloudflare tunnel
│   ├── external-services/    # External service proxies
│   ├── longhorn/             # Longhorn storage
│   ├── metallb/              # MetalLB load balancer
│   ├── monitoring/           # Prometheus/Grafana
│   ├── rancher/              # K8s management
│   ├── sealed-secrets        # Encrypted secret management (Bitnami Sealed Secrets)
│   └── traefik/              # Traefik ingress controller
├── apps/                     # Application workloads (flat structure, auto-discovered)
│   ├── postgresql/           # Shared database
│   ├── valkey/               # Redis-compatible cache
│   ├── home-assistant/       # Home automation
│   └── ...                   # Other apps (affine, freshrss, it-tools, etc.)
├── scripts/                  # Utility scripts
│   └── kryptos/              # Secret management (Go tool)
└── docs/                     # Documentation
```

### Separation of Concerns

#### Infrastructure (`infrastructure/`)

Foundational components for the cluster:

- **Purpose**: Core services required for cluster operation
- **Organization**: By function (ingress, security, networking, storage,
  monitoring)
- **Pattern**: Per-component directories managed as ArgoCD Applications
- **Examples**: Traefik, Cert-Manager, MetalLB, Longhorn

#### Applications (`apps/`)

User-facing workloads and services:

- **Purpose**: Business logic and user applications
- **Organization**: Flat structure in `apps/` directory (auto-discovered)
- **Pattern**: Helm-based or manifest-based
- **Examples**: Affine, FreshRSS, Home Assistant, IT Tools, SearXNG

### Application Organization

Applications use a flat structure for simplicity:

1. **Auto-Discovery**: Applications are automatically discovered via Git
   directory generator
2. **Simple Navigation**: Flat structure makes it easy to find apps
3. **Namespace Isolation**: Each app gets its own namespace matching the
   app name
4. **No Manual Configuration**: Adding an app is as simple as creating a
   directory in `apps/`
5. **Git as Source of Truth**: Directory existence = app deployment

**Structure**:

- **Flat Structure**: All applications are in `apps/` directory (no categories)
- **Auto-Discovery**: Applications are automatically discovered via Git
  directory generator
- **Namespace**: Each app gets its own namespace matching the app name

---

## Application Architecture

### Application Structure Patterns

Applications follow one of two patterns based on deployment method:

#### Pattern 1: Helm-Based Applications

For applications with Helm charts:

```text
apps/<app-name>/
├── kustomization.yaml      # Root kustomization (ArgoCD entry point)
├── values.yaml             # Helm values overrides (if using Helm)
├── ingress/                 # Traefik IngressRoute
│   ├── ingressroute.yaml
│   └── kustomization.yaml
├── secrets/                 # SealedSecret resources
│   └── kustomization.yaml
└── jobs/                    # Optional: CronJobs
    └── kustomization.yaml
```

**Example**: `apps/postgresql/kustomization.yaml`

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: postgresql

helmCharts:
  - name: postgresql
    repo: https://charts.bitnami.com/bitnami
    version: 16.7.27 # Pinned version
    releaseName: postgresql
    namespace: postgresql
    valuesFile: values.yaml

resources:
  - jobs # Database creation jobs
  - secrets # SealedSecrets
```

**Key Characteristics**:

- Uses `helmCharts` in kustomization
- Helm chart version is **always pinned**
- Values overridden via `values.yaml`
- Additional resources (ingress, secrets) via `resources`

#### Pattern 2: Manifest-Based Applications

For applications without Helm charts or custom deployments:

```text
apps/<app-name>/
├── kustomization.yaml      # Root kustomization (ArgoCD entry point)
├── base/                   # Base Kubernetes manifests (if not using Helm)
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
├── ingress/                 # Traefik IngressRoute
│   ├── ingressroute.yaml
│   └── kustomization.yaml
└── secrets/                 # Optional: SealedSecrets
    └── kustomization.yaml
```

**Example**: `apps/it-tools/kustomization.yaml`

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: it-tools

resources:
  - base # Raw Kubernetes manifests
  - ingress # Traefik IngressRoute
```

**Key Characteristics**:

- Raw Kubernetes manifests in `base/`
- No Helm charts
- Full control over manifests
- Kustomize for customization

### Root Kustomization Requirement

**Critical**: Every application **must** have a root `kustomization.yaml` at
the application directory level. This is the entry point that ArgoCD uses.

**Path**: `apps/<app-name>/kustomization.yaml`

**Why**:

- ArgoCD ApplicationSet references this path
- Kustomize requires root kustomization
- Enables resource composition (Helm + manifests)

### Ingress Pattern

All applications use **Traefik IngressRoute** for ingress:

**Location**: `apps/<app-name>/ingress/`

**Example**: `ingressroute.yaml`

```text
apiVersion: traefik.containo.us/v1alpha1
kind: IngressRoute
metadata:
  name: my-app
  namespace: my-app
spec:
  entryPoints:
    - web
    - websecure
  routes:
    - match: Host(`my-app.example.com`)
      kind: Rule
      services:
        - name: my-app-service
          port: 80
  tls:
    certResolver: letsencrypt-prod
```

**Benefits**:

- Automatic SSL/TLS via Cert-Manager
- Traefik-native configuration
- Advanced routing capabilities

### Secret Management Pattern

Secrets are managed via **Sealed Secrets**:

**Location**: `apps/<app-name>/secrets/`

**Workflow**:

1. Generate secrets using `scripts/kryptos/`
2. Kryptos creates SealedSecret resources
3. SealedSecrets committed to Git (encrypted)
4. Sealed Secrets Controller unseals in cluster
5. Regular Kubernetes secrets created automatically

**Why Sealed Secrets**:

- Git-safe: Encrypted secrets can be committed
- GitOps-friendly: Secrets in Git like other resources
- Automatic unsealing: Controller handles decryption
- RBAC-controlled: Only controller can unseal

---

## Infrastructure Architecture

### Infrastructure Components

Infrastructure components are organized by function in `infrastructure/`:

#### 1. GitOps (`infrastructure/argocd/`)

**Purpose**: ArgoCD configuration and management

**Structure**:

```text
infrastructure/argocd/
├── kustomization.yaml
├── ingress/               # ArgoCD UI ingress
├── patches/               # Kustomize patches
└── secrets/               # Admin and repo credentials (sealed)
```

**Key Features**:

- Self-managed: ArgoCD manages itself
- RBAC and repo configuration via patches/secrets
- Ingress for UI access

#### 2. Ingress (`infrastructure/traefik/`)

**Purpose**: Edge router and ingress controller

**Structure**:

```text
infrastructure/traefik/
├── kustomization.yaml
├── certificates/          # Certificate definitions
└── values.yaml            # Helm values (Traefik chart)
```

**Key Features**:

- Helm-based deployment
- SSL/TLS termination
- Automatic certificate management
- Load balancing

#### 3. Security (`infrastructure/cert-manager/`)

**Purpose**: Automatic SSL/TLS certificate management

**Structure**:

```text
infrastructure/cert-manager/
├── kustomization.yaml
├── values.yaml
├── issuers/               # Let's Encrypt issuers
└── secrets/               # Cloudflare API credentials (sealed)
```

**Key Features**:

- Let's Encrypt integration
- Cloudflare DNS01 challenge
- Automatic certificate renewal
- Production and staging issuers

#### 4. Networking (`infrastructure/metallb/` and

`infrastructure/external-services/`)

**Purpose**: Load balancing and external service proxying

**MetalLB**:

- L2 load balancer for bare metal
- IP address pool management
- Service type LoadBalancer support

**External Services**:

- Proxies external services through Traefik
- Services: Proxmox, UniFi, OPNSense, etc.
- Endpoints, Services, and IngressRoutes

#### 5. Storage (`infrastructure/longhorn/`)

**Purpose**: Distributed block storage

**Key Features**:

- Replicated storage
- Backup capabilities
- Volume management UI
- StorageClass for dynamic provisioning

#### 6. Monitoring (`infrastructure/monitoring/`)

**Purpose**: Prometheus and Grafana monitoring

**Components**:

- Prometheus: Metrics collection
- Grafana: Visualization and dashboards
- AlertManager: Alerting
- Node Exporter: Node metrics
- Kube State Metrics: Kubernetes metrics

> Monitoring is intentionally commented out in
> `argocd/infrastructure/kustomization.yaml`; enable it explicitly before
> syncing if required.

---

## Network Architecture

### Network Flow

```text
Internet
   │
   ▼
MetalLB (Load Balancer)
   │
   ▼
Traefik (Ingress Controller)
   │
   ├──► Applications (Affine, Home Assistant, etc.)
   ├──► External Services (Proxmox, UniFi, etc.)
   └──► Platform Services (ArgoCD UI, Grafana, etc.)
```

### Ingress Flow

1. **External Request** → MetalLB LoadBalancer IP
2. **MetalLB** → Routes to Traefik Service
3. **Traefik** → Matches IngressRoute rules
4. **Cert-Manager** → Provides SSL/TLS certificates
5. **Traefik** → Routes to backend Service
6. **Service** → Routes to Pod endpoints

### DNS and Certificates

- **DNS**: Managed via Cloudflare
- **Certificates**: Let's Encrypt via Cert-Manager
- **Challenge**: DNS01 challenge (Cloudflare API)
- **Renewal**: Automatic via Cert-Manager

### Service Discovery

- **Internal**: Kubernetes DNS (`<service>.<namespace>.svc.cluster.local`)
- **External**: Traefik IngressRoutes with FQDNs
- **Load Balancing**: Traefik handles load balancing

---

## Storage Architecture

### Storage Strategy

**Primary Storage**: Longhorn (distributed block storage)

**Storage Classes**:

- `longhorn`: Default storage class
- Replication: Configurable per volume
- Backup: Integrated backup system

### Volume Management

**Pattern**: Applications request PersistentVolumeClaims (PVCs)

**Example**:

```text
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data
spec:
  storageClassName: longhorn
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### Backup Strategy

- **Longhorn Backups**: Volume-level backups
- **Application Backups**: Application-specific (e.g., PostgreSQL dumps)
- **Git Backups**: Configuration in Git (automatic)

---

## Security Architecture

### Secret Management

**Sealed Secrets** workflow:

```text
Plain Secret → kubeseal → SealedSecret → Git → Controller → Secret
```

1. **Generation**: `scripts/kryptos/` creates SealedSecrets
2. **Storage**: SealedSecrets committed to Git (encrypted)
3. **Unsealing**: Sealed Secrets Controller decrypts in cluster
4. **Usage**: Applications use regular Kubernetes secrets

### RBAC

- **ArgoCD RBAC**: Configured via `argocd-rbac-cm.yaml`
- **Kubernetes RBAC**: Per-namespace service accounts
- **Principle of Least Privilege**: Minimal required permissions

### Network Security

- **Ingress**: Traefik with SSL/TLS termination
- **Internal**: Kubernetes network policies (optional)
- **External**: Firewall rules at network level

### Certificate Security

- **Let's Encrypt**: Free, automated certificates
- **Renewal**: Automatic via Cert-Manager
- **Staging**: Test certificates before production

---

## Data Flow & Dependencies

### Application Dependencies

```text
PostgreSQL (Core)
   ├──► Affine
   └──► FreshRSS

Valkey (Core)
   └──► (Future cache/session storage)

Traefik (Platform)
   └──► All Applications (Ingress)

Cert-Manager (Platform)
   └──► Traefik (Certificates)

Longhorn (Platform)
   └──► All Applications (Storage)
```

### Deployment Order

1. **Platform Components** (infrastructure first):
   - MetalLB
   - Traefik
   - Cert-Manager
   - Longhorn
   - Monitoring

2. **Core Services** (dependencies):
   - PostgreSQL
   - Valkey

3. **Applications** (depend on core):
   - Affine (depends on PostgreSQL)
   - FreshRSS (depends on PostgreSQL)
   - Other applications (Home Assistant, IT Tools, etc.)

### Data Flow

**User Request Flow**:

```text
User → DNS → MetalLB → Traefik → Application Pod → Database/Storage
```

**GitOps Flow**:

```text
Developer → Git → ArgoCD → Kubernetes API → Pods
```

**Monitoring Flow**:

```text
Pods → Prometheus → Grafana → User
```

---

## Design Decisions

### Why App-of-Apps?

**Decision**: Use ArgoCD App-of-Apps pattern

**Rationale**:

- Centralized management
- Consistent configuration
- Easy to scale
- Industry best practice

**Alternatives Considered**:

- Individual Application resources (too many files)
- Single ApplicationSet (less flexibility)
- **Chosen**: App-of-Apps (best balance)

### Why Manual Sync?

**Decision**: Disable automated sync

**Rationale**:

- Safety: Prevent accidental deployments
- Control: Review changes before applying
- Stability: Avoid reconciliation loops
- Audit: Explicit sync actions

**Trade-offs**:

- Requires manual intervention
- Slower deployment cycle
- **Acceptable**: Safety and control prioritized

### Why Categorize Applications?

**Decision**: Organize applications by category

**Rationale**:

- Better organization
- Easier navigation
- Policy application
- Dependency management

**Categories**:

- Core: Critical infrastructure
- Productivity: User-facing apps
- Utilities: Helper tools
- Management: Ops tools
- Archive: Deprecated apps

### Why Sealed Secrets?

**Decision**: Use Sealed Secrets for secret management

**Rationale**:

- Git-safe: Encrypted secrets in Git
- GitOps-friendly: Secrets as code
- Automatic: Controller handles unsealing
- Secure: RBAC-controlled

**Alternatives Considered**:

- External Secrets Operator (more complex)
- Vault (overkill for homelab)
- **Chosen**: Sealed Secrets (simple, effective)

### Why Helm + Kustomize?

**Decision**: Use both Helm and Kustomize

**Rationale**:

- **Helm**: For applications with charts (easier)
- **Kustomize**: For custom manifests (flexibility)
- **Combined**: Best of both worlds

**Pattern**:

- Helm charts via Kustomize `helmCharts`
- Additional resources via Kustomize `resources`
- Unified entry point: Root `kustomization.yaml`

### Why Platform vs Applications?

**Decision**: Separate platform and applications

**Rationale**:

- Clear separation of concerns
- Platform: Infrastructure
- Applications: Workloads
- Different lifecycles
- Easier management

---

## Related Documentation

- [Application Development Guide](./APPLICATION_DEVELOPMENT.md) - How to
  add and manage applications
- [Platform Components](./PLATFORM_COMPONENTS.md) - Detailed platform
  component documentation
- [Troubleshooting](./TROUBLESHOOTING.md) - Common issues and solutions
- [Security](./SECURITY.md) - Security best practices
- [Main README](../README.md) - Repository overview and quickstart

---

## See Also

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Kustomize Documentation](https://kustomize.io/)
- [Helm Documentation](https://helm.sh/docs/)
- [Sealed Secrets Documentation](https://github.com/bitnami-labs/sealed-secrets)
