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
   `ssh://git@source.example.com/example-org/argo-apps.git`
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
kubectl apply -k apps/infra/argocd/
```

This command:

- Creates the `argocd` namespace
- Installs ArgoCD using manifests from `apps/infra/argocd/`
- Waits for ArgoCD server to be ready

### Step 1.2: Get Initial Admin Password

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
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

Create the Git repository secret manually:

```bash
# Create repository secret
kubectl create secret generic gitlab-repo-secret \
  -n argocd \
  --from-literal=type=git \
  --from-literal=url=ssh://git@source.example.com/example-org/argo-apps.git \
  --from-file=sshPrivateKey=~/.ssh/id_rsa

# Label the secret
kubectl label secret gitlab-repo-secret \
  -n argocd \
  argocd.argoproj.io/secret-type=repository
```

### Step 2.2: Apply Root Bootstrap

```bash
kubectl apply -f argocd/root.yaml
```

This creates the root ArgoCD Application, which applies the `argocd/`
kustomization and deploys the single ApplicationSet. The ApplicationSet then
generates every app from `apps/*/*/config.yaml`, grouped by tier via sync
waves:

- ✅ **Infra tier** (waves -1..3) — cert-manager, metallb, traefik, longhorn,
  external-services, cloudflare-ddns, cloudflared, authentik, metrics-server,
  priority-classes, sealed-secrets, and the self-managing argocd Application
- ✅ **Data tier** (wave 4) — postgresql, valkey
- ✅ **Services tier** (wave 5) — harbor, headlamp
- ✅ **User tier** (wave 6) — docuseal, joplin, litellm, memos, onetimesecret,
  open-webui, privatebin, searxng, snapotter, stirling-pdf

> The argocd Application is generated like any other app (from
> `apps/infra/argocd/config.yaml`) but ArgoCD itself was installed manually in
> Stage 1; sync it deliberately once Traefik is up (see Stage 3).

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
- Manually sync applications in tier order (infra -1..3 → data 4 →
  services 5 → user 6)

### Step 2.4: Wait for Traefik

Once Traefik is deployed, ArgoCD will have ingress available at
`https://argo.example.com` (if DNS is configured).

---

## Stage 3: ArgoCD Self-Management

After Traefik is deployed and ArgoCD has ingress, enable self-management.
There is no separate `argocd.yaml` to apply — the ApplicationSet already
generated an `argocd` Application from `apps/infra/argocd/config.yaml`. Sync it
deliberately to hand ArgoCD's own lifecycle to GitOps:

```bash
argocd app sync argocd
# or, in the ArgoCD UI, sync the "argocd" Application
```

Once synced, this Application manages ArgoCD itself via GitOps:

- Updates ArgoCD configuration from `apps/infra/argocd/`
- Manages ArgoCD ingress via Traefik
- Enables the full GitOps lifecycle for ArgoCD

**Note**: This Application syncs ArgoCD's own configuration. Monitor carefully
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
argocd                  Synced        Healthy
authentik               Synced        Healthy
cert-manager            Synced        Healthy
cloudflare-ddns         Synced        Healthy
cloudflared             Synced        Healthy
docuseal                Synced        Healthy
external-services       Synced        Healthy
harbor                  Synced        Healthy
headlamp                Synced        Healthy
joplin                  Synced        Healthy
litellm                 Synced        Healthy
longhorn                Synced        Healthy
memos                   Synced        Healthy
metallb                 Synced        Healthy
metrics-server          Synced        Healthy
onetimesecret           Synced        Healthy
open-webui              Synced        Healthy
postgresql              Synced        Healthy
priority-classes        Synced        Healthy
privatebin              Synced        Healthy
searxng                 Synced        Healthy
sealed-secrets          Synced        Healthy
snapotter               Synced        Healthy
stirling-pdf            Synced        Healthy
traefik                 Synced        Healthy
valkey                  Synced        Healthy
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

# Test SSH connection to GitLab
ssh -T git@source.example.com

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

1. **Sync Applications**: Apps are generated by the ApplicationSet from
   `apps/*/*/config.yaml`; sync them in tier order
2. **Configure DNS**: Point `argo.example.com` to MetalLB LoadBalancer IP
3. **Access Services**: All services will be available via Traefik ingress
4. **Manage Secrets**: Use `kryptos/` for secret management (see
   [docs/SECURITY.md](../docs/SECURITY.md))

---

## Architecture Notes

### Why Separate Bootstrap?

- **ArgoCD must exist first** to process GitOps Applications
- **Git repository credentials** must be configured before sync
- **Traefik provides ingress** but is deployed via ArgoCD
- **Self-management** enables full GitOps lifecycle after bootstrap

### File Structure

```text
argocd/
├── README.md                    # This file
├── root.yaml                    # Root Application (deploys argocd/)
├── kustomization.yaml           # Control-plane bootstrap
└── apps-set.yaml                # ApplicationSet (git files generator)

apps/
├── infra/<name>/config.yaml     # Generated as infra-tier Applications
├── data/<name>/config.yaml      # Generated as data-tier Applications
├── services/<name>/config.yaml  # Generated as services-tier Applications
└── user/<name>/config.yaml      # Generated as user-tier Applications

Note: argocd/root.yaml creates an Application pointing at the argocd/ path,
which deploys the single ApplicationSet. The ApplicationSet generates every
app (including the self-managing argocd Application) from
apps/*/*/config.yaml.
```

---

## Summary

The 3-stage bootstrap process solves the circular dependency:

1. **Stage 1**: Manual ArgoCD install → ArgoCD exists
2. **Stage 2**: GitOps infrastructure → Traefik provides ingress
3. **Stage 3**: Self-management → Full GitOps lifecycle

This ensures a clean, repeatable bootstrap process for fresh clusters.
