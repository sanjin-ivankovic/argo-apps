# Bootstrap Guide for Fresh k3s Cluster

This guide walks through deploying the entire GitOps stack on a **fresh k3s
cluster** where ArgoCD doesn't exist yet.

## Problem Statement

The deployment has a **chicken-and-egg problem**:

- ArgoCD needs to exist to manage applications via GitOps
- But ArgoCD itself is managed via GitOps
- ArgoCD needs Git repository credentials before it can sync
- ArgoCD needs Traefik for ingress, but Traefik is deployed via ArgoCD

## Solution: 3-Stage Bootstrap Process

### Stage 1 Overview: Manual ArgoCD Installation

Install ArgoCD manually using `kubectl` and `kustomize`. This bypasses the
GitOps loop.

### Stage 2 Overview: Infrastructure Bootstrap

Configure Git repository and deploy infrastructure (without ArgoCD) via ArgoCD.

### Stage 3 Overview: ArgoCD Self-Management

After Traefik is deployed, enable ArgoCD to manage itself via GitOps.

---

## Prerequisites

1. **Fresh k3s cluster** (or compatible Kubernetes cluster)
2. **kubectl** configured and connected to cluster
3. **kustomize** installed (or `kubectl kustomize` available)
4. **SSH key** with access to
   `ssh://git@gitlab.example.com:2424/homelab/argo-apps.git`
5. **Sealed Secrets Controller** (optional, for secret management)

### Install Sealed Secrets Controller (if not present)

```bash
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml
```

---

## Stage 1: Manual ArgoCD Installation

### Step 1.1: Install ArgoCD

```bash
cd /path/to/argo-apps
chmod +x bootstrap/install-argocd.sh
./bootstrap/install-argocd.sh
```

This script:

- Creates the `argocd` namespace
- Installs ArgoCD using manifests from `infrastructure/argocd/`
- Waits for ArgoCD server to be ready
- Displays next steps

### Step 1.2: Get Initial Admin Password

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```

Save this password - you'll need it to access ArgoCD UI.

### Step 1.3: Access ArgoCD UI (Port-Forward)

Since Traefik isn't deployed yet, use port-forward:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Then access: **<https://localhost:8080>** (accept the self-signed
certificate)

- Username: `admin`
- Password: (from Step 1.2)

---

## Stage 2: Infrastructure Bootstrap

### Step 2.1: Configure Git Repository

```bash
chmod +x bootstrap/configure-repo.sh
./bootstrap/configure-repo.sh
```

This script:

- Prompts for SSH private key path
- Creates Kubernetes secret for Git repository
- Optionally adds repository via ArgoCD CLI (if installed)

**Manual Alternative** (if script fails):

```bash
# Create repository secret manually
kubectl create secret generic gitlab-repo-secret \
  -n argocd \
  --from-literal=type=git \
  --from-literal=url=ssh://git@gitlab.example.com:2424/homelab/argo-apps.git \
  --from-file=sshPrivateKey=~/.ssh/id_rsa

# Label the secret
kubectl label secret gitlab-repo-secret \
  -n argocd \
  argocd.argoproj.io/secret-type=repository
```

### Step 2.2: Apply Root Bootstrap

```bash
kubectl apply -f bootstrap/root.yaml
```

This creates the root ArgoCD Application that deploys all infrastructure:

- ✅ cert-manager (Wave 0)
- ✅ metallb (Wave 1)
- ✅ traefik (Wave 1)
- ✅ longhorn (Wave 1)
- ✅ external-services (Wave 3)
- ✅ rancher (Wave 3)
- ✅ apps-applicationset (Wave 4)
- ❌ **ArgoCD excluded** (installed manually)

> Monitoring is intentionally commented out in
> `argocd/infrastructure/kustomization.yaml`; enable it deliberately before
> syncing if you want the monitoring stack.

### Step 2.3: Monitor Deployment

**Via kubectl:**

```bash
kubectl get applications -n argocd
kubectl get pods -n traefik
kubectl get pods -n cert-manager
```

**Via ArgoCD UI:**

- Port-forward: `kubectl port-forward svc/argocd-server -n argocd 8080:443`
- Access: <https://localhost:8080>
- Manually sync applications in order (Wave 0 → Wave 1 → Wave 3 → Wave 4)

### Step 2.4: Wait for Traefik

Once Traefik is deployed, ArgoCD will have ingress available at
`https://argo.example.com` (if DNS is configured).

---

## Stage 3: ArgoCD Self-Management

After Traefik is deployed and ArgoCD has ingress, enable self-management:

```bash
kubectl apply -f argocd/infrastructure/argocd.yaml
```

This creates an ArgoCD Application that manages ArgoCD itself via GitOps:

- Updates ArgoCD configuration from `infrastructure/argocd/`
- Manages ArgoCD ingress via Traefik
- Enables full GitOps lifecycle for ArgoCD

**Note**: This Application will sync ArgoCD configuration. Monitor carefully
on first sync.

---

## Verification

### Check All Applications

```bash
kubectl get applications -n argocd
```

Expected output:

```text
NAME                    SYNC STATUS   HEALTH STATUS
apps-applicationset     Synced        Healthy
argocd                  Synced        Healthy
cert-manager            Synced        Healthy
external-services       Synced        Healthy
infrastructure          Synced        Healthy
longhorn                Synced        Healthy
metallb                 Synced        Healthy
rancher                 Synced        Healthy
traefik                 Synced        Healthy
```

### Access ArgoCD UI

Once Traefik is deployed and DNS is configured:

- **URL**: <https://argo.example.com>
- **Username**: `admin`
- **Password**: (from Stage 1.2, or reset if needed)

### Check Infrastructure Components

```bash
# Traefik
kubectl get pods -n traefik

# Cert-Manager
kubectl get pods -n cert-manager

# MetalLB
kubectl get pods -n metallb-system

# Longhorn
kubectl get pods -n longhorn-system
```

---

## Troubleshooting

### ArgoCD Server Not Starting

```bash
kubectl get pods -n argocd
kubectl describe pod -n argocd -l app.kubernetes.io/name=argocd-server
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server
```

### Git Repository Connection Issues

```bash
# Check repository secret
kubectl get secret gitlab-repo-secret -n argocd -o yaml

# Test SSH connection to GitLab (custom port)
ssh -T -p 2424 git@gitlab.example.com

# Check ArgoCD repo server logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server
```

### Applications Not Syncing

```bash
# Check application status
kubectl describe application <app-name> -n argocd

# Check sync status
kubectl get applications -n argocd -o wide

# Manual sync via CLI
argocd app sync <app-name>
```

### Traefik Not Available

If Traefik fails to deploy:

- Check MetalLB: `kubectl get svc -n traefik`
- Check Traefik pods: `kubectl get pods -n traefik`
- Check logs: `kubectl logs -n traefik -l app.kubernetes.io/name=traefik`

---

## Next Steps

After bootstrap is complete:

1. **Sync Applications**: Applications are auto-discovered via ApplicationSet
2. **Configure DNS**: Point `argo.example.com` to MetalLB LoadBalancer IP
3. **Access Services**: All services will be available via Traefik ingress
4. **Manage Secrets**: Use `scripts/kryptos/` for secret management (see
   docs/SECURITY.md)

---

## Architecture Notes

### Why Separate Bootstrap?

- **ArgoCD must exist first** to process GitOps Applications
- **Git repository credentials** must be configured before sync
- **Traefik provides ingress** but is deployed via ArgoCD
- **Self-management** enables full GitOps lifecycle after bootstrap

### File Structure

```text
bootstrap/
├── README.md                    # This file
├── DEPLOYMENT-FLOW.md           # Detailed deployment flow
├── install-argocd.sh           # Stage 1: Manual ArgoCD install
├── configure-repo.sh            # Stage 2.1: Git repo config
└── root.yaml                    # Stage 2.2: Root Application (deploys argocd/)

argocd/
├── kustomization.yaml           # All infrastructure apps
├── applications/
│   └── apps-set.yaml           # ApplicationSet for auto-discovery
└── infrastructure/
    ├── argocd.yaml             # ArgoCD self-management
    ├── cert-manager.yaml
    ├── traefik.yaml
    └── ... (all infrastructure apps)

Note: bootstrap/root.yaml creates an Application pointing to argocd/ path,
which deploys all infrastructure including ArgoCD self-management.
```

---

## Summary

The 3-stage bootstrap process solves the circular dependency:

1. **Stage 1**: Manual ArgoCD install → ArgoCD exists
2. **Stage 2**: GitOps infrastructure → Traefik provides ingress
3. **Stage 3**: Self-management → Full GitOps lifecycle

This ensures a clean, repeatable bootstrap process for fresh clusters.
