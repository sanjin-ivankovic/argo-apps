# Quick Reference Guide

## Table of Contents

- [ArgoCD Commands](#argocd-commands)
- [Kubectl Commands](#kubectl-commands)
- [Application Paths](#application-paths)
- [Namespace Reference](#namespace-reference)
- [Access URLs](#access-urls)
- [Port Forwarding](#port-forwarding)
- [Secret Management](#secret-management)
- [Common Workflows](#common-workflows)
- [File Locations](#file-locations)
- [Useful Aliases](#useful-aliases)
- [Related Documentation](#related-documentation)

---

## ArgoCD Commands

### Authentication

```bash
# Login to ArgoCD
argocd login argo.example.com

# Login with username/password
argocd login argo.example.com --username admin

# Get current context
argocd account get-user-info
```

### Application Management

```bash
# List all applications
argocd app list

# Get application status
argocd app get <app-name>

# Get application details (JSON)
argocd app get <app-name> -o json

# Sync an application
argocd app sync <app-name>

# Sync all applications
argocd app sync --all

# Sync with prune (delete resources not in Git)
argocd app sync <app-name> --prune

# Force sync (ignore differences)
argocd app sync <app-name> --force

# Watch application sync
argocd app wait <app-name>

# Refresh application (detect changes)
argocd app get <app-name> --refresh

# Get application manifests
argocd app manifests <app-name>

# Get application history
argocd app history <app-name>

# Rollback to previous revision
argocd app rollback <app-name> <revision>

# Delete an application
argocd app delete <app-name>

# View application diff
argocd app diff <app-name>

# View application logs
argocd app logs <app-name> --tail=50
```

### Repository Management

```bash
# List repositories
argocd repo list

# Get repository details
argocd repo get <repo-url>

# Refresh repository
argocd repo get <repo-url> --refresh

# Add repository (if needed)
argocd repo add <repo-url>
```

---

## Kubectl Commands

### Cluster Status

```bash
# Check node status
kubectl get nodes

# Check node details
kubectl describe node <node-name>

# Get resource usage
kubectl top nodes
kubectl top pods -A

# Quick health check
kubectl get nodes && kubectl get applications -n argocd
```

### ArgoCD Resources

```bash
# Get all ArgoCD applications
kubectl get applications -n argocd

# Get application details
kubectl get application <app-name> -n argocd -o yaml

# Watch application sync status
kubectl get applications -n argocd -w

# Describe application
kubectl describe application <app-name> -n argocd

# Get ApplicationSet
kubectl get applicationset -n argocd

# Describe ApplicationSet
kubectl describe applicationset apps-set -n argocd
```

### Pods

```bash
# Get pods across all namespaces
kubectl get pods -A

# Get pods for specific namespace
kubectl get pods -n <namespace>

# Get pods with wide output
kubectl get pods -n <namespace> -o wide

# Describe pod
kubectl describe pod <pod-name> -n <namespace>

# View pod logs
kubectl logs <pod-name> -n <namespace>

# View previous container logs
kubectl logs <pod-name> -n <namespace> --previous

# Follow logs
kubectl logs -f <pod-name> -n <namespace>

# Execute command in pod
kubectl exec -it <pod-name> -n <namespace> -- /bin/bash
```

### Services & Networking

```bash
# Get services
kubectl get svc -n <namespace>

# Get services across all namespaces
kubectl get svc -A

# Describe service
kubectl describe svc <service-name> -n <namespace>

# Get endpoints
kubectl get endpoints -n <namespace>

# Get IngressRoutes (Traefik)
kubectl get ingressroute -n <namespace>
kubectl get ingressroute -A

# Describe IngressRoute
kubectl describe ingressroute <name> -n <namespace>
```

### Storage

```bash
# Get persistent volume claims
kubectl get pvc -n <namespace>
kubectl get pvc -A

# Get persistent volumes
kubectl get pv

# Get volume attachments
kubectl get volumeattachment

# Get Longhorn volumes
kubectl get volumes.longhorn.io -n longhorn-system
```

### Secrets & ConfigMaps

```bash
# Get secrets
kubectl get secrets -n <namespace>

# Get SealedSecrets
kubectl get sealedsecrets -n <namespace>

# Describe secret
kubectl describe secret <secret-name> -n <namespace>

# Get ConfigMaps
kubectl get configmap -n <namespace>
```

### Certificates

```bash
# Get certificates
kubectl get certificates -A

# Get certificate requests
kubectl get certificaterequests -A

# Describe certificate
kubectl describe certificate <cert-name> -n <namespace>

# Get issuers
kubectl get issuers -n <namespace>
```

### Events & Debugging

```bash
# Get events
kubectl get events -n <namespace>

# Get events sorted by time
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Get events across all namespaces
kubectl get events -A --sort-by='.lastTimestamp'

# Get all resources in namespace
kubectl get all -n <namespace>
```

### Namespaces

```bash
# List all namespaces
kubectl get ns

# Get namespace details
kubectl describe ns <namespace>

# Get resources in namespace
kubectl get all -n <namespace>
```

---

## Application Paths

### Core Applications

| Application    | Path              | Namespace    |
| -------------- | ----------------- | ------------ |
| **Gitea**      | `apps/gitea`      | `gitea`      |
| **PostgreSQL** | `apps/postgresql` | `postgresql` |
| **Valkey**     | `apps/valkey`     | `valkey`     |

### Productivity Applications

| Application        | Path                  | Namespace        |
| ------------------ | --------------------- | ---------------- |
| **Affine**         | `apps/affine`         | `affine`         |
| **FreshRSS**       | `apps/freshrss`       | `freshrss`       |
| **Home Assistant** | `apps/home-assistant` | `home-assistant` |

### Utility Applications

| Application      | Path                | Namespace      |
| ---------------- | ------------------- | -------------- |
| **IT Tools**     | `apps/it-tools`     | `it-tools`     |
| **MySpeed**      | `apps/myspeed`      | `myspeed`      |
| **Omni Tools**   | `apps/omni-tools`   | `omni-tools`   |
| **PrivateBin**   | `apps/privatebin`   | `privatebin`   |
| **SearXNG**      | `apps/searxng`      | `searxng`      |
| **Stirling PDF** | `apps/stirling-pdf` | `stirling-pdf` |

### Management Applications

| Application | Path           | Namespace       |
| ----------- | -------------- | --------------- |
| **Rancher** | `apps/rancher` | `cattle-system` |

### Infrastructure Components

| Component        | Path                               | Namespace         |
| ---------------- | ---------------------------------- | ----------------- |
| **ArgoCD**       | `infrastructure/argocd`            | `argocd`          |
| **Traefik**      | `infrastructure/traefik`           | `traefik`         |
| **Cert-Manager** | `infrastructure/cert-manager`      | `cert-manager`    |
| **MetalLB**      | `infrastructure/metallb`           | `metallb-system`  |
| **Longhorn**     | `infrastructure/longhorn`          | `longhorn-system` |
| **Monitoring**   | `infrastructure/monitoring`        | `monitoring`      |
| **External**     | `infrastructure/external-services` | Various           |

---

## Namespace Reference

### Application Namespaces

- `affine` - Affine
- `freshrss` - FreshRSS
- `home-assistant` - Home Assistant
- `it-tools` - IT Tools
- `myspeed` - MySpeed
- `omni-tools` - Omni Tools
- `postgresql` - PostgreSQL
- `privatebin` - PrivateBin
- `searxng` - SearXNG
- `stirling-pdf` - Stirling PDF
- `valkey` - Valkey
- `cattle-system` - Rancher

### Infrastructure Namespaces

- `argocd` - ArgoCD
- `traefik` - Traefik
- `cert-manager` - Cert-Manager
- `metallb-system` - MetalLB
- `longhorn-system` - Longhorn
- `monitoring` - Prometheus/Grafana
- `kube-system` - Kubernetes system components

---

## Access URLs

### Management Interfaces

- **ArgoCD UI**: <https://argo.example.com>
- **Grafana**: <https://grafana.example.com>
- **Longhorn UI**: <https://longhorn.example.com>
- **Rancher**: <https://rancher.example.com>

### Application URLs

- **Affine**: <https://affine.example.com>
- **FreshRSS**: <https://rss.example.com>
- **Home Assistant**: <https://home.example.com>
- **IT Tools**: <https://it-tools.example.com>
- **MySpeed**: <https://myspeed.example.com>
- **Omni Tools**: <https://omni-tools.example.com>
- **PrivateBin**: <https://paste.example.com>
- **SearXNG**: <https://search.example.com>
- **Stirling PDF**: <https://pdf.example.com>

### External Services (Proxied)

- **Proxmox**: <https://pve.example.com>
- **UniFi**: <https://unifi.example.com>
- **OPNSense**: <https://fw.example.com>
- **Nextcloud**: <https://nextcloud.example.com>
- **Immich**: <https://immich.example.com>
- **Duplicati**: <https://duplicati.example.com>
- **Semaphore**: <https://semaphore.example.com>
- **Servarr**: <https://servarr.example.com>
- **Technitium**: <https://dns1.example.com>
- **Unraid**: <https://unraid.example.com>

---

## Port Forwarding

### ArgoCD

```bash
# Port forward to ArgoCD UI
kubectl port-forward -n argocd svc/argocd-server 8080:443

# Access at: https://localhost:8080
```

### Grafana

```bash
# Port forward to Grafana
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80

# Access at: http://localhost:3000
```

### Longhorn

```bash
# Port forward to Longhorn UI
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80

# Access at: http://localhost:8080
```

### Applications

```bash
# Port forward to any service
kubectl port-forward -n <namespace> svc/<service-name> <local-port>:<service-port>

# Example: Gitea
kubectl port-forward -n gitea svc/gitea-http 8080:3000
```

---

## Secret Management

### Generate Sealed Secrets

```bash
# Navigate to kryptos directory
cd scripts/kryptos

# Run the interactive tool
./kryptos

# Select app from menu
# Follow prompts to generate secrets
# Kryptos will create sealed secrets in app's secrets/ directory
```

### Verify Secrets

```bash
# Check SealedSecrets
kubectl get sealedsecrets -n <namespace>

# Check if secrets were unsealed
kubectl get secrets -n <namespace>

# Describe SealedSecret
kubectl describe sealedsecret <name> -n <namespace>

# Check sealed-secrets controller
kubectl get pods -n kube-system | grep sealed-secrets
kubectl logs -n kube-system -l name=sealed-secrets-controller --tail=50
```

---

## Common Workflows

### Add New Application

```bash
# 1. Create directory structure
mkdir -p apps/<app-name>/{ingress,secrets}

# 2. Create kustomization.yaml and manifests
#    ArgoCD ApplicationSet auto-discovers apps/*; no manual edits needed.

# 3. Generate secrets (if needed)
cd scripts/kryptos && ./kryptos

# 4. Test locally
kubectl kustomize apps/<app-name>

# 5. Commit and push
git add .
git commit -m "Add <app-name>"
git push origin main

# 6. Sync in ArgoCD
argocd app sync <app-name>
```

### Update Application

```bash
# 1. Make changes to manifests/values

# 2. Test locally
kubectl kustomize apps/<app-name>

# 3. Commit and push
git add .
git commit -m "Update <app-name>"
git push origin main

# 4. Sync in ArgoCD
argocd app sync <app-name>

# 5. Monitor sync
argocd app wait <app-name>
```

### Update Helm Chart Version

```bash
# 1. Edit kustomization.yaml
vim apps/<app-name>/kustomization.yaml
# Update version in helmCharts section

# 2. Update values.yaml if needed
vim apps/<app-name>/values.yaml

# 3. Test locally
kubectl kustomize apps/<app-name>

# 4. Commit and push
git commit -am "Update <app-name> to chart v<version>"
git push origin main

# 5. Sync in ArgoCD
argocd app sync <app-name>
```

### Rollback Application

```bash
# Via ArgoCD
argocd app history <app-name>
argocd app rollback <app-name> <revision>

# Via Git
git log --oneline apps/<app-name>
git checkout <commit-hash> -- apps/<app-name>
git commit -m "Rollback <app-name> to <commit-hash>"
git push origin main
argocd app sync <app-name>
```

### Troubleshoot Application

```bash
# 1. Check application status
argocd app get <app-name>

# 2. Check pod status
kubectl get pods -n <namespace>

# 3. View pod logs
kubectl logs <pod-name> -n <namespace>

# 4. Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# 5. Describe pod
kubectl describe pod <pod-name> -n <namespace>

# 6. Check ArgoCD sync status
kubectl get application <app-name> -n argocd -o yaml
```

### Restart Application

```bash
# Scale down and up
kubectl scale deployment <app-name> -n <namespace> --replicas=0
kubectl scale deployment <app-name> -n <namespace> --replicas=1

# Or delete pod (will be recreated)
kubectl delete pod <pod-name> -n <namespace>
```

### Check Application Health

```bash
# Quick health check
kubectl get pods -n <namespace>
kubectl get svc -n <namespace>
kubectl get ingressroute -n <namespace>

# Detailed check
kubectl get all -n <namespace>
kubectl describe deployment <app-name> -n <namespace>
```

---

## File Locations

### Key Configuration Files

- **App-of-Apps**: `argocd/app-of-apps.yaml`
- **ApplicationSet**: `argocd/applications/apps-set.yaml`
- **Infrastructure Apps**: `argocd/infrastructure/*.yaml`
- **Sealed Secrets Tool**: `scripts/kryptos/`
- **Secret Configs**: `scripts/kryptos/configs/`

### Application Structure

```text
apps/<app-name>/
├── kustomization.yaml      # Root kustomization (required)
├── values.yaml             # Helm values (if Helm-based)
├── base/                   # Base manifests (if manifest-based)
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
├── ingress/
│   ├── ingressroute.yaml
│   └── kustomization.yaml
├── secrets/
│   └── kustomization.yaml
└── jobs/                   # Optional
    └── kustomization.yaml
```

### Infrastructure Structure

```text
infrastructure/
├── argocd/
├── traefik/
├── cert-manager/
├── metallb/
├── external-services/
├── longhorn/
└── monitoring/   # optional; commented out in argocd/infrastructure/kustomization.yaml
```

---

## Useful Aliases

Add these to your `~/.bashrc` or `~/.zshrc`:

```bash
# ArgoCD shortcuts
alias argo='argocd'
alias argo-list='argocd app list'
alias argo-sync='argocd app sync'
alias argo-status='argocd app get'

# Kubectl shortcuts
alias k='kubectl'
alias kg='kubectl get'
alias kd='kubectl describe'
alias kl='kubectl logs'
alias kaf='kubectl apply -f'
alias kdf='kubectl delete -f'

# Namespace shortcuts
alias kga='kubectl get all'
alias kgp='kubectl get pods'
alias kgs='kubectl get svc'
alias kgi='kubectl get ingressroute'

# Application shortcuts
alias apps='kubectl get applications -n argocd'
alias app-status='kubectl get application'

# Quick checks
alias health='kubectl get nodes && kubectl get applications -n argocd'
alias pods-all='kubectl get pods -A'
alias events='kubectl get events -A --sort-by='\''.lastTimestamp'\'''

# Port forwarding shortcuts
alias argo-port='kubectl port-forward -n argocd svc/argocd-server 8080:443'
alias grafana-port='kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80'
alias longhorn-port='kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80'
```

### Function Aliases

```bash
# Quick pod logs
klog() {
    kubectl logs -f "$1" -n "${2:-default}"
}

# Quick pod exec
kexec() {
    kubectl exec -it "$1" -n "${2:-default}" -- /bin/bash
}

# Quick describe
kdesc() {
    kubectl describe "$1" "$2" -n "${3:-default}"
}

# Quick get with namespace
kgn() {
    kubectl get "$1" -n "$2"
}
```

---

## Quick Diagnostic Commands

### Cluster Health

```bash
# One-liner health check
kubectl get nodes && kubectl get applications -n argocd && kubectl get pods -A | grep -vE "(Running|Completed)"
```

### Application Status

```bash
# Check all applications
kubectl get applications -n argocd

# Check specific application
argocd app get <app-name>

# Check pods for app
kubectl get pods -n <namespace>
```

### Resource Usage

```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods -A

# Specific namespace
kubectl top pods -n <namespace>
```

### Storage Status

```bash
# All PVCs
kubectl get pvc -A

# Longhorn volumes
kubectl get volumes.longhorn.io -n longhorn-system

# Volume attachments
kubectl get volumeattachment
```

### Networking

```bash
# All IngressRoutes
kubectl get ingressroute -A

# All Services
kubectl get svc -A

# Certificates
kubectl get certificates -A
```

---

## Related Documentation

- [Architecture Documentation](./ARCHITECTURE.md) - System architecture
- [Application Development Guide](./APPLICATION_DEVELOPMENT.md) - Adding
  applications
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues and solutions
- [Security Guide](./SECURITY.md) - Security best practices
- [Main README](../README.md) - Repository overview

---

## See Also

- [ArgoCD CLI Reference][argocd-cli]
- [Kubectl Cheat
  Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [Kustomize Documentation](https://kustomize.io/)

[argocd-cli]: https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd/
