# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Repository Overview

This is an ArgoCD-based GitOps repository for managing a homelab Kubernetes
cluster. The repository uses the **app-of-apps pattern** with **Git directory
generator** for automatic application discovery.

**Critical**: Auto-sync is **intentionally disabled** across all applications.
After pushing changes to the `main` branch, you **must manually sync** in the
ArgoCD UI at <https://argo.example.com>.

**Git Repository**: `ssh://git@gitlab.example.com:2424/homelab/argo-apps.git`
**Custom Helm Charts**: `https://git.example.com/homelab/helm-charts.git` (OCI:
`oci://registry.example.com/homelab/helm-charts`)

## Architecture Patterns

### App-of-Apps Entry Point

**Bootstrap**: Apply `bootstrap/root.yaml` OR `argocd/kustomization.yaml` to
bootstrap the entire stack
**Flow**: Bootstrap → Infrastructure Apps + ApplicationSet → Auto-discovers
apps in `apps/`

### Automatic App Discovery

Applications are **automatically discovered** using a Git directory generator.
Simply add a directory to `apps/` and ArgoCD finds it automatically.

```text
# argocd/applications/apps-set.yaml
generators:
  - git:
      directories:
        - path: apps/* # Auto-discovers all subdirectories
```

**Namespace Rule**: App name = namespace name (Exception: Rancher uses
`cattle-system` via explicit override in its kustomization.yaml)

### Two Application Patterns

#### 1. Helm-Based Applications (Most Apps)

**Custom Charts** (from `oci://registry.example.com/homelab/helm-charts`):

- affine, freshrss, home-assistant, it-tools, myspeed, omni-tools,
  privatebin, searxng, stirling-pdf, cloudflared

**Public Charts** (from standard Helm repos):

- PostgreSQL (`https://charts.bitnami.com/bitnami`)
- Valkey (`https://charts.bitnami.com/bitnami`)
- Rancher (`https://releases.rancher.com/server-charts/stable`)

Structure:

```text
apps/<app>/
├── kustomization.yaml      # Helm chart definition
├── values.yaml             # Helm values overrides
├── ingress/                # Traefik IngressRoute
│   ├── ingressroute.yaml
│   └── kustomization.yaml
└── secrets/                # SealedSecrets
    ├── <app>-secret.yaml
    └── kustomization.yaml
```

kustomization.yaml example:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: myapp
helmCharts:
  - name: myapp
    repo: oci://registry.example.com/homelab/helm-charts # OR public repo
    version: 1.0.0 # Always pinned
    releaseName: myapp
    namespace: myapp
    valuesFile: values.yaml
resources:
  - ingress
  - secrets
```

#### 2. Manifest-Based Applications

Structure:

```text
apps/<app>/
├── kustomization.yaml
├── base/                   # Raw K8s manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
└── ingress/
    └── ingressroute.yaml
```

## Common Commands

### ArgoCD CLI

```bash
# Login
argocd login argo.example.com

# List applications
argocd app list

# Get app status
argocd app get <app-name>

# Sync application (REQUIRED - auto-sync disabled)
argocd app sync <app-name>

# Watch sync
argocd app wait <app-name>

# Rollback
argocd app rollback <app-name> <revision>
```

### kubectl

```bash
# Get all ArgoCD applications
kubectl get applications -n argocd

# Watch sync status
kubectl get applications -n argocd -w

# Test manifests before commit
kubectl apply -k apps/<app-name> --dry-run=server

# Get pods across namespaces
kubectl get pods -A

# Check certificates
kubectl get certificates -A

# Check Traefik IngressRoutes
kubectl get ingressroute -A
```

### Development Workflow

```bash
# Test Kustomize build locally (ALWAYS do this before committing)
kubectl apply -k apps/<app> --dry-run=server
kubectl apply -k infrastructure/<component> --dry-run=server

# Commit changes
git add apps/<app>/
git commit -m "Update <app>"
git push

# Then manually sync in ArgoCD UI
```

## Secret Management

**Critical**: NEVER commit plaintext secrets. All secrets must be encrypted
using Sealed Secrets.

### Using Kryptos (Go-based Secret Management)

```bash
# Interactive TUI for secret generation
cd scripts/kryptos
./kryptos

# Follow interactive prompts to:
# 1. Select app
# 2. Choose secret to generate
# 3. Enter values (or use auto-generation keywords)
```

### Kryptos Features

- **Interactive TUI**: User-friendly menu-driven interface
- **Auto-generation keywords**:
  - `secure` — 32-character secure password
  - `strong` — 32-character password with symbols
  - `apikey` — 64-character hex API key
  - `passphrase` — Random 4-word passphrase
- **YAML configuration**: Apps defined in
  `scripts/kryptos/configs/<app-name>.yaml`
- **Automated output**: SealedSecret YAML written to `apps/<app>/secrets/`

### Configuration Example

Each app has a config file at `scripts/kryptos/configs/<app-name>.yaml`:

```text
app_name: "myapp"
display_name: "My App"
namespace: "myapp"

secrets:
  - name: "myapp-admin"
    display_name: "Admin Secret"
    type: "Opaque"
    keys: ["username", "password"]
    description: "Administrator credentials"

  - name: "myapp-database"
    display_name: "Database Secret"
    type: "Opaque"
    keys: ["password"]
    description: "Database password"
```

### Verification

```bash
# Verify SealedSecret exists
kubectl get sealedsecrets -n <namespace>

# Check if secret was unsealed by controller
kubectl get secrets -n <namespace>

# Check sealed-secrets controller logs
kubectl logs -n kube-system -l name=sealed-secrets-controller
```

## Ingress & Networking

### Traefik IngressRoute (NOT standard Kubernetes Ingress)

**Pattern**: Use Traefik's `IngressRoute` CRD, not `kind: Ingress`
**Domain**: `*.example.com` with wildcard TLS certificate
**TLS**: Handled automatically - no explicit `tls:` section needed in most cases

Standard IngressRoute:

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

### TLS Certificates

- Managed by cert-manager (deployed via multi-source ArgoCD Application)
- Let's Encrypt with Cloudflare DNS01 challenge
- Wildcard certificate for `*.example.com`
- Configuration in `infrastructure/cert-manager/`

## CI/CD Pipeline

### Overview

The repository includes a GitLab CI/CD pipeline for automated validation and
dependency management:

- **Lint**: YAML syntax validation with yamllint
- **Renovate**: Automated dependency updates for Helm charts and Docker images
- **Validate**: Kustomize builds and Kubernetes schema validation
- **Security**: Secret scanning and privilege checking

### Pipeline Configuration

**Files:**

- `.gitlab-ci.yml` - Pipeline definition
- `renovate.json` - Renovate configuration
- `docs/CI-CD-PIPELINE.md` - Detailed documentation

### Required CI/CD Variables

Configure in GitLab: **Settings > CI/CD > Variables**

<!-- markdownlint-disable MD013 -->

| Variable                    | Description                                                                                |
| --------------------------- | ------------------------------------------------------------------------------------------ |
| `RENOVATE_TOKEN`            | GitLab Personal Access Token for Renovate (scopes: `api`, `read_user`, `write_repository`) |
| `RENOVATE_GITHUB_COM_TOKEN` | Optional GitHub token to avoid rate limiting when fetching release info                    |

<!-- markdownlint-enable MD013 -->

### Scheduled Pipeline Setup

1. Navigate to **CI/CD > Schedules**
2. Create schedule: "Renovate Dependency Updates"
3. Cron: `0 3 * * 1-5` (3 AM weekdays)
4. Target Branch: `main`

### Renovate Features

- **Helm Charts**: Tracks updates for both public repos and custom OCI registry
- **Docker Images**: Updates container images in manifests
- **Grouped Updates**: Changes grouped by app directory for atomic updates
- **Conservative Strategy**: 3-30 day minimum release age depending on component
  criticality
- **Manual Approval**: All updates require MR review and manual merge
- **Security Priority**: Immediate PRs for security vulnerabilities

### Validation Jobs (Dynamic Child Pipeline)

**How it works:**

1. **Generate**: Python script analyzes changes and generates child pipeline
2. **Trigger**: Child pipeline runs with separate jobs per affected app
3. **Parallel**: Each app/component validates independently

**For each affected manifest:**

- Kustomize build validation
- Kubernetes schema validation with kubeconform

**Benefits:**

- Parallel execution for speed
- Clear per-app job visualization
- Scalable to any number of apps
- GitLab-native child pipeline feature

### Important Notes

- Pipeline validates manifests but doesn't deploy
- After merging changes, **manually sync in ArgoCD UI** (auto-sync disabled)
- Renovate creates MRs with dependency updates - review carefully before
  merging
- See `docs/CI-CD-PIPELINE.md` for detailed usage and troubleshooting

## Infrastructure Components

Located in `infrastructure/` and deployed via
`argocd/infrastructure/*.yaml`:

<!-- markdownlint-disable MD013 -->

| Component         | Namespace         | Purpose               | Notes                                  |
| ----------------- | ----------------- | --------------------- | -------------------------------------- |
| ArgoCD            | `argocd`          | GitOps controller     | Self-managing, sync-wave: 0            |
| Traefik           | `traefik`         | Ingress controller    | Chart v37.3.0, IngressRoute CRDs       |
| Cert-Manager      | `cert-manager`    | TLS certificates      | Multi-source Application               |
| MetalLB           | `metallb-system`  | L2 load balancer      | For bare metal                         |
| Longhorn          | `longhorn-system` | Distributed storage   | Default storage class                  |
| Monitoring        | `monitoring`      | Prometheus + Grafana  | kube-prometheus-stack (commented out)  |
| Cloudflared       | `cloudflared`     | Cloudflare tunnel     | Custom Helm chart                      |
| External Services | various           | Service proxies       | Proxmox, UniFi, OpnSense, GitLab, etc. |
| Sealed Secrets    | `kube-system`     | Secret encryption     | Controller for SealedSecrets           |
| Rancher           | `cattle-system`   | Kubernetes management | Optional management UI                 |

<!-- markdownlint-enable MD013 -->

## Shared PostgreSQL Pattern

Central PostgreSQL cluster at `apps/postgresql/` serves multiple applications:

- affine — AI-powered note-taking platform
- freshrss — RSS feed aggregator

**Database Creation**: Automated jobs in `apps/postgresql/jobs/` create
databases for each app
**Credentials**: Stored as SealedSecrets in `apps/postgresql/secrets/`

**Note**: Jobs for `joplin` and `transcribe` remain as reference (apps are
archived)

## Adding New Applications

### Step-by-Step Process

1. **Create directory structure**:

   ```bash
   mkdir -p apps/myapp/{ingress,secrets}
   ```

2. **Create kustomization.yaml** (Helm example):

   ```text
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   namespace: myapp
   helmCharts:
     - name: myapp
       repo: oci://registry.example.com/homelab/helm-charts
       version: 1.0.0
       releaseName: myapp
       namespace: myapp
       valuesFile: values.yaml
   resources:
     - ingress
     - secrets
   ```

3. **Create IngressRoute**:

   ```bash
   # Create apps/myapp/ingress/ingressroute.yaml
   # Create apps/myapp/ingress/kustomization.yaml
   ```

4. **Generate secrets**:

   ```bash
   cd scripts/kryptos
   # Create config file: configs/myapp.yaml (see Configuration Example above)
   ./kryptos
   # Select myapp from menu and follow prompts
   ```

5. **Test locally**:

   ```bash
   kubectl apply -k apps/myapp --dry-run=server
   ```

6. **Commit and sync**:

```bash
git add apps/myapp/
git commit -m "Add myapp application"
git push
# Manually sync ApplicationSet in ArgoCD UI
# Then manually sync the new myapp Application
```

**No ApplicationSet editing required** - Git directory generator
auto-discovers the new app!

## Troubleshooting

### Application Won't Sync

```bash
# Check application status
kubectl get application <app> -n argocd -o yaml

# View sync errors
argocd app get <app>

# Test Kustomize build
kubectl apply -k apps/<app> --dry-run=server

# Check ArgoCD logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

### Secret Issues

```bash
# Verify SealedSecret resource
kubectl get sealedsecret <name> -n <namespace> -o yaml

# Check if unsealed
kubectl get secret <name> -n <namespace>

# Check controller logs
kubectl logs -n kube-system -l name=sealed-secrets-controller

# Verify kubeseal can reach controller
kubeseal --fetch-cert
```

### Certificate Issues

```bash
# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager

# Check certificate status
kubectl describe certificate <name> -n <namespace>

# Verify DNS challenge
dig _acme-challenge.<domain>.example.com
```

### Longhorn + Multipathd Issues (Ubuntu 24.04)

**Symptom**: Volumes fail to format with "device apparently in use"

**Fix** (on all worker nodes):

```bash
cat > /etc/multipath.conf << 'EOF'
defaults {
    user_friendly_names yes
}
blacklist {
    device {
        vendor "IET"
        product "VIRTUAL-DISK"
    }
}
EOF
systemctl restart multipathd
```

## CI/CD Validation Pipeline

Located at `.gitea/workflows/validate.yaml`. Runs on all pushes and PRs to
`main` branch.

**Pipeline Jobs**:

1. **detect-changes**: Identifies changed manifests (apps/, infrastructure/,
   argocd/)
2. **lint-yaml**: YAML syntax validation with yamllint
3. **build-and-validate**: Kustomize build + kubeconform schema validation
4. **security-scan**: Scans for plaintext secrets, privileged containers,
   security misconfigurations

**Tools Used**:

- yamllint: YAML syntax
- Kustomize v5.5.0: Manifest building with Helm support
- kubeconform v0.6.7: K8s schema validation
- Kubernetes target version: v1.31.0

**On PRs**: Only validates changed manifests
**On main branch**: Validates all manifests

## Critical Gotchas

1. **Auto-sync disabled everywhere**: Must manually sync in ArgoCD UI after
   pushing changes
2. **Git directory generator**: Apps auto-discovered from `apps/*` - no
   manual ApplicationSet editing
3. **Traefik uses IngressRoute CRD**: Standard `kind: Ingress` won't work
4. **Wildcard TLS cert**: Managed in `infrastructure/traefik/certificates/`
   - no per-app cert needed
5. **Namespace = app name**: ArgoCD uses `{{.path.basename}}` for namespace
   (except Rancher)
6. **Longhorn is default storage class**: Don't specify `storageClassName`
   unless overriding
7. **Custom Helm charts**: Most apps use
   `oci://registry.example.com/homelab/helm-charts` from separate repo
8. **Sealed Secrets only**: Never commit plaintext secrets - use
   `scripts/kryptos/`
9. **Test before committing**: Always run
   `kubectl apply -k apps/<app> --dry-run=server`
10. **Manual sync required**: After git push, manually sync in ArgoCD UI

## External Resources

- **ArgoCD UI**: <https://argo.example.com>
- **Custom Helm Charts Repository**:
  <https://gitlab.example.com/homelab/helm-charts.git>
- **Helm Charts OCI Registry**: oci://registry.example.com/homelab/helm-charts
- **Grafana**: <https://grafana.example.com> (if monitoring enabled)
- **Longhorn UI**: <https://longhorn.example.com>
