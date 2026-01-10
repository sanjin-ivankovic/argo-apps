# Detailed Technical Guide

This guide provides comprehensive technical details for deploying,
configuring, maintaining, and troubleshooting the Kubernetes homelab
infrastructure.

> **Audience**: This document is for operators and contributors who need
> deep technical implementation details. For a quick overview, see the
> [main README](../README.md).

---

## Table of Contents

- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Bootstrap Process](#bootstrap-process)
- [Adding Applications](#adding-applications)
  - [Step-by-Step Process](#step-by-step-process)
  - [Application Structure Templates](#application-structure-templates)
- [Configuration](#configuration)
  - [Helm Chart Sources](#helm-chart-sources)
  - [Database Architecture](#database-architecture)
  - [Ingress & Networking](#ingress--networking)
- [Security & Secrets](#security--secrets)
  - [Kryptos Workflow](#kryptos-workflow)
  - [Secret Verification](#secret-verification)
- [Maintenance](#maintenance)
  - [Safe Node Reboots](#safe-node-reboots)
  - [Helm Chart Updates](#helm-chart-updates)
  - [Backup Procedures](#backup-procedures)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

#### 1. Kubernetes Cluster (v1.34+)

**Supported Distributions**:

- K3s (recommended for homelab)
- K8s (vanilla Kubernetes)
- K0s, MicroK8s, or compatible distributions

**Minimum Requirements**:

- **Nodes**: 2+ (1 master + 1+ workers)
- **CPU**: 4+ cores per node
- **Memory**: 8GB+ RAM per node
- **Storage**: 50GB+ available for Longhorn

#### 2. kubectl CLI

Install kubectl compatible with your cluster version:

```bash
# macOS
brew install kubectl

# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify installation
kubectl version --client
```

#### 3. ArgoCD CLI (Optional but Recommended)

```bash
# macOS
brew install argocd

# Linux
curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
sudo install -m 555 argocd /usr/local/bin/argocd

# Verify installation
argocd version --client
```

#### 4. Kubeseal CLI (for Secret Management)

```bash
# macOS
brew install kubeseal

# Linux
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/kubeseal-0.24.0-linux-amd64.tar.gz
tar -xvzf kubeseal-0.24.0-linux-amd64.tar.gz
sudo install -m 755 kubeseal /usr/local/bin/kubeseal
```

---

### Bootstrap Process

Follow these steps to deploy the entire infrastructure from scratch.

#### Step 1: Clone Repository

```bash
git clone <your-repo-url>
cd argo-apps
```

#### Step 2: Deploy ArgoCD

#### Option A: Bootstrap Application (Recommended)

```bash
kubectl apply -f bootstrap/root.yaml
```

This creates the root Application that manages ArgoCD and all
infrastructure components.

#### Option B: Direct Kustomize Deployment

```bash
kubectl apply -f argocd/kustomization.yaml
```

#### Step 3: Wait for ArgoCD to be Ready

```bash
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=argocd-server \
  -n argocd \
  --timeout=300s
```

#### Step 4: Get ArgoCD Initial Password

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

#### Step 5: Access ArgoCD UI

**Port Forward** (if no ingress available yet):

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Then access: `https://localhost:8080`

**Login Credentials**:

- Username: `admin`
- Password: (from Step 4)

#### Step 6: Sync Infrastructure Components

In the ArgoCD UI, manually sync infrastructure applications **in this order**:

1. **argocd** — ArgoCD self-management
2. **sealed-secrets** — Secret encryption controller
3. **cert-manager** — Certificate management
4. **metallb** — Load balancer
5. **traefik** — Ingress controller
6. **longhorn** — Distributed storage
7. **cloudflared** — Cloudflare tunnel
8. **external-services** — External service proxies
9. **rancher** (optional) — Kubernetes management UI

> **Note**: Wait for each component to become healthy before proceeding to
> the next.

#### Step 7: Sync ApplicationSet

Sync the `apps` ApplicationSet in ArgoCD UI. This will automatically
discover and create Applications for all directories in `apps/`.

#### Step 8: Sync Individual Applications

Once applications appear in ArgoCD, manually sync each one as needed.

---

## Adding Applications

### Step-by-Step Process

#### 1. Create Application Directory

```bash
mkdir -p apps/my-app/{ingress,secrets}
```

#### 2. Create Kustomization

**For Helm-based apps** (using custom OCI charts):

```text
# apps/my-app/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

helmCharts:
  - name: my-app
    repo: oci://registry.example.com/helm-charts
    version: 1.0.0
    releaseName: my-app
    namespace: my-app
    valuesFile: values.yaml

resources:
  - ingress
  - secrets
```

**For Helm-based apps** (using public repositories):

```text
# apps/my-app/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

helmCharts:
  - name: my-app
    repo: https://charts.example.com/
    version: 1.2.3
    releaseName: my-app
    namespace: my-app
    valuesFile: values.yaml

resources:
  - ingress
  - secrets
```

**For manifest-based apps**:

```text
# apps/my-app/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

resources:
  - base
  - ingress
  - secrets
```

#### 3. Create Helm Values (if using Helm)

```text
# apps/my-app/values.yaml
replicaCount: 1

image:
  repository: my-app
  tag: "1.0.0"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "256Mi"
    cpu: "200m"
```

#### 4. Create IngressRoute

```text
# apps/my-app/ingress/ingressroute.yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: my-app-ingressroute
  namespace: my-app
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`myapp.example.com`)
      kind: Rule
      services:
        - name: my-app
          port: 80
```

```text
# apps/my-app/ingress/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

resources:
  - ingressroute.yaml
```

#### 5. Generate Secrets (if needed)

Use the Kryptos tool to generate sealed secrets:

```bash
cd scripts/kryptos

# Run the interactive TUI
./kryptos

# Follow prompts to:
# 1. Select or create app configuration
# 2. Enter secret values (or use auto-generation)
# 3. Generate SealedSecret YAML
```

**Kryptos Configuration Example**:

```text
# scripts/kryptos/configs/my-app.yaml
app_name: "my-app"
display_name: "My Application"
namespace: "my-app"

secrets:
  - name: "my-app-credentials"
    display_name: "Admin Credentials"
    type: "Opaque"
    keys: ["admin-username", "admin-password"]
    description: "Administrator login credentials"

  - name: "my-app-api-key"
    display_name: "API Key"
    type: "Opaque"
    keys: ["api-key"]
    description: "External API authentication key"
```

Move generated SealedSecret to app directory:

```bash
# Kryptos outputs to apps/my-app/secrets/
# Verify the file was created
ls apps/my-app/secrets/my-app-sealed-secret.yaml
```

Create secrets kustomization:

```text
# apps/my-app/secrets/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

resources:
  - my-app-sealed-secret.yaml
```

#### 6. Test Locally

```bash
kubectl apply -k apps/my-app --dry-run=server
```

This validates the manifests without applying them to the cluster.

#### 7. Commit and Push

```bash
git add apps/my-app/
git commit -m "feat(apps): add my-app application"
git push
```

#### 8. Sync in ArgoCD

- Navigate to ArgoCD UI
- Refresh the `apps` ApplicationSet
- `my-app` will appear automatically
- Click "Sync" on the `my-app` Application

**No ApplicationSet editing required!** The Git directory generator
automatically discovers the new app.

---

### Application Structure Templates

#### Helm-Based Application

```text
apps/my-helm-app/
├── kustomization.yaml      # Helm chart definition
├── values.yaml             # Helm values overrides
├── ingress/
│   ├── ingressroute.yaml   # Traefik IngressRoute
│   └── kustomization.yaml
└── secrets/                # Optional
    ├── my-app-secret.yaml  # SealedSecret
    └── kustomization.yaml
```

#### Manifest-Based Application

```text
apps/my-manifest-app/
├── kustomization.yaml      # References base resources
├── base/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── kustomization.yaml
├── ingress/
│   ├── ingressroute.yaml
│   └── kustomization.yaml
└── secrets/                # Optional
    ├── my-app-secret.yaml  # SealedSecret
    └── kustomization.yaml
```

---

## Configuration

### Helm Chart Sources

Applications use charts from multiple sources:

#### Custom Helm Charts (OCI Registry)

**Registry**: `oci://registry.example.com/helm-charts`

Applications using custom charts:

- `affine`
- `freshrss`
- `home-assistant`
- `it-tools`
- `myspeed`
- `omni-tools`
- `privatebin`
- `searxng`
- `stirling-pdf`
- `cloudflared`

#### Public Helm Repositories

<!-- markdownlint-disable MD013 -->

| Application   | Repository                                | Chart                   |
| ------------- | ----------------------------------------- | ----------------------- |
| PostgreSQL    | `https://charts.bitnami.com/bitnami`      | `postgresql`            |
| Valkey        | `https://charts.bitnami.com/bitnami`      | `valkey`                |
| Rancher       | `https://releases.rancher.com/`           | `rancher`               |
| Traefik       | `https://traefik.github.io/charts`        | `traefik`               |
| Longhorn      | `https://charts.longhorn.io`              | `longhorn`              |
| Monitoring    | `https://prometheus-community.github.io/` | `kube-prometheus-stack` |
| cert-manager  | `https://charts.jetstack.io`              | `cert-manager`          |
| SealedSecrets | `https://bitnami-labs.github.io/`         | `sealed-secrets`        |

<!-- markdownlint-enable MD013 -->

> **Note**: Monitoring stack is currently inactive (commented out in
> `argocd/infrastructure/kustomization.yaml`). To enable, uncomment
> `monitoring.yaml` before syncing.

---

### Database Architecture

#### Shared PostgreSQL Cluster

Central PostgreSQL deployment in `apps/postgresql/` provides database
services to multiple applications.

**Connected Applications**:

- **affine** — AI-powered note-taking platform
- **freshrss** — RSS feed aggregator

**Database Provisioning**: Automated database creation using Kubernetes
Jobs in `apps/postgresql/jobs/`:

- `affine-db-create-job.yaml`
- `freshrss-db-create-job.yaml`
- `joplin-db-create-job.yaml` *reference only — app archived*
- `transcribe-db-create-job.yaml` *reference only — never deployed*

**Credentials Management**:

- Database passwords stored as SealedSecrets in `apps/postgresql/secrets/`
- Each application has its own database user and credentials
- Root PostgreSQL admin credentials also sealed

**Example Job Structure**:

```text
apiVersion: batch/v1
kind: Job
metadata:
  name: affine-db-create-job
  namespace: postgresql
spec:
  template:
    spec:
      containers:
        - name: db-create
          image: postgres:16
          command:
            - /bin/sh
            - -c
            - |
              psql -h postgresql-postgresql.postgresql.svc.cluster.local \
                   -U postgres -c "CREATE DATABASE affine;"
              psql -h postgresql-postgresql.postgresql.svc.cluster.local \
                   -U postgres -c "CREATE USER affine WITH PASSWORD '$AFFINE_DB_PASSWORD';"
              psql -h postgresql-postgresql.postgresql.svc.cluster.local \
                   -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE affine TO affine;"
          env:
            - name: AFFINE_DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: affine-db-credentials
                  key: password
      restartPolicy: OnFailure
```

---

### Ingress & Networking

#### Traefik IngressRoutes

**Important**: Use Traefik IngressRoute CRD (**NOT** standard Kubernetes
Ingress).

**Domain Pattern**: `*.example.com` with wildcard TLS certificates

**Standard IngressRoute Template**:

```text
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: <app>-ingressroute
  namespace: <app>
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`<app>.example.com`)
      kind: Rule
      services:
        - name: <service-name>
          port: <port>
```

**TLS Notes**:

- Traefik handles TLS termination using wildcard certificates
- No explicit `tls:` section needed in most IngressRoutes
- Certificates managed by cert-manager

#### TLS Certificates

**cert-manager Configuration**:

- Deployed via multi-source ArgoCD Application
- Helm chart: `https://charts.jetstack.io`
- Additional resources from Git: `infrastructure/cert-manager/`
- Wildcard certificate for `*.example.com`
- Uses Let's Encrypt with DNS01 challenge (Cloudflare)

**Certificate Issuers**:

- ClusterIssuer: `letsencrypt-prod` (production)
- ClusterIssuer: `letsencrypt-staging` (testing)

**Verifying Certificates**:

```bash
# Check certificate status
kubectl get certificates -A

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager

# Verify DNS propagation
dig _acme-challenge.example.com TXT
```

#### External Service Proxies

Non-Kubernetes services can be proxied through Traefik using the pattern
in `infrastructure/external-services/`:

1. **Create Endpoints** pointing to external IP
2. **Create Service** referencing the Endpoints
3. **Create IngressRoute** routing to the Service

**Example** (Proxmox):

```text
# Endpoints
apiVersion: v1
kind: Endpoints
metadata:
  name: proxmox
  namespace: external-services
subsets:
  - addresses:
      - ip: 192.168.1.100
    ports:
      - port: 8006
        name: https

---
# Service
apiVersion: v1
kind: Service
metadata:
  name: proxmox
  namespace: external-services
spec:
  ports:
    - port: 8006
      targetPort: 8006
      protocol: TCP
      name: https

---
# IngressRoute
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: proxmox
  namespace: external-services
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`proxmox.example.com`)
      kind: Rule
      services:
        - name: proxmox
          port: 8006
          scheme: https
```

---

## Security & Secrets

### Kryptos Workflow

**Kryptos** is a custom Go-based CLI tool for managing SealedSecrets.

#### Features

- **Interactive TUI** — User-friendly menu-driven interface
- **YAML Configuration** — App secrets defined in `configs/<app>.yaml`
- **Auto-Generation** — Magic keywords for secure password generation:
  - `secure` — 32-character secure password
  - `strong` — 32-character password with symbols
  - `apikey` — 64-character hex API key
  - `passphrase` — Random 4-word passphrase
- **Built-in Validation** — Ensures kubeseal is available and cluster
  connectivity
- **Automated Output** — SealedSecret YAML written to `apps/<app>/secrets/`

#### Usage

```bash
cd scripts/kryptos
./kryptos
```

**Interactive Workflow**:

1. Select application from list (or create new config)
2. Choose secret to generate
3. Enter values for each key (or use auto-generation keywords)
4. Kryptos generates SealedSecret YAML
5. File saved to `apps/<app>/secrets/`

#### Creating New App Configuration

```text
# scripts/kryptos/configs/my-new-app.yaml
app_name: "my-new-app"
display_name: "My New Application"
namespace: "my-new-app"

secrets:
  - name: "my-new-app-admin"
    display_name: "Administrator Credentials"
    type: "Opaque"
    keys: ["username", "password"]
    description: "Admin user credentials for web UI"

  - name: "my-new-app-database"
    display_name: "Database Connection"
    type: "Opaque"
    keys: ["db-host", "db-user", "db-password"]
    description: "PostgreSQL connection credentials"
```

**Restart Kryptos** after creating new configs to see them in the menu.

---

### Secret Verification

After deploying SealedSecrets, verify they are unsealed correctly:

```bash
# Check SealedSecret resource exists
kubectl get sealedsecrets -n <namespace>

# Verify the unsealed Secret was created
kubectl get secrets -n <namespace>

# Check sealed-secrets controller logs if issues occur
kubectl logs -n kube-system -l name=sealed-secrets-controller
```

**CRITICAL**:

- ⛔ **Never commit plain-text secrets to Git**
- ✅ **Always use SealedSecrets for GitOps**
- 🔐 **Backup the sealed-secrets key** (see [Backup
  Procedures](#backup-procedures))

---

## Maintenance

### Safe Node Reboots

When applying system updates (OS patches, kernel upgrades) to nodes:

#### ⚠️ Important Constraints

- **Never reboot all nodes simultaneously** — Cluster will lose quorum
- **Master nodes**: Maintain quorum (keep 2+ online in multi-master setup)
- **Worker nodes**: Reboot one at a time only
- **Longhorn volumes**: Require clean detach/reattach between reboots

#### Worker Node Reboot Procedure

```bash
# 1. Cordon the node (prevent new pod scheduling)
kubectl cordon worker-node-1

# 2. Drain the node gracefully
kubectl drain worker-node-1 \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --grace-period=300 \
  --timeout=600s

# 3. SSH to node and reboot
ssh worker-node-1 sudo reboot

# 4. Wait for node to come back online and become Ready
kubectl get nodes -w

# 5. Uncordon the node (allow scheduling again)
kubectl uncordon worker-node-1

# 6. Verify pods rescheduled correctly
kubectl get pods -A -o wide | grep worker-node-1
```

**Wait 5-10 minutes between worker reboots** to ensure:

- Longhorn volumes reattach properly
- Pods stabilize and pass health checks
- Storage replication completes

#### Master Node Reboot Procedure

**Only if you have 3+ master nodes (HA setup)**:

```bash
# Same procedure as worker, but:
# - Only reboot one master at a time
# - Ensure quorum maintained (n/2 + 1 masters online)
# - Wait longer between reboots (10-15 minutes)
```

---

### Helm Chart Updates

Update application versions by editing the chart version in
`kustomization.yaml`:

```text
# apps/my-app/kustomization.yaml
helmCharts:
  - name: my-app
    repo: oci://registry.example.com/helm-charts
    version: 1.2.4 # ← Update this version
    releaseName: my-app
    namespace: my-app
    valuesFile: values.yaml
```

**Update Workflow**:

```bash
# 1. Edit kustomization.yaml with new version
vim apps/my-app/kustomization.yaml

# 2. Test rendering locally (optional)
kubectl apply -k apps/my-app --dry-run=server

# 3. Commit changes
git commit -am "chore(my-app): update chart to v1.2.4"
git push

# 4. Sync in ArgoCD UI
# Navigate to my-app Application and click "Sync"
```

---

### Backup Procedures

#### 1. Git Repository (Automatic)

All configuration is version-controlled in Git. Ensure:

- Regular commits with meaningful messages
- Remote repository backups (GitHub, GitLab, etc.)
- Protected branches for production

#### 2. PostgreSQL Databases

**Manual Backup**:

```bash
# Backup single database
kubectl exec -it postgresql-postgresql-0 -n postgresql -- \
  pg_dump -U postgres affine > affine-backup-$(date +%Y%m%d).sql

# Backup all databases
kubectl exec -it postgresql-postgresql-0 -n postgresql -- \
  pg_dumpall -U postgres > postgres-full-backup-$(date +%Y%m%d).sql
```

**Automated via CronJob** (Recommended):

Create backup CronJob in `apps/postgresql/jobs/postgres-backup-cronjob.yaml`:

```text
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: postgresql
spec:
  schedule: "0 2 * * *" # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: postgres:16
              command:
                - /bin/sh
                - -c
                - |
                  pg_dumpall -h postgresql-postgresql.postgresql.svc.cluster.local \
                             -U postgres > /backup/postgres-$(date +\%Y\%m\%d-\%H\%M\%S).sql
              volumeMounts:
                - name: backup-volume
                  mountPath: /backup
          restartPolicy: OnFailure
          volumes:
            - name: backup-volume
              persistentVolumeClaim:
                claimName: postgres-backup-pvc
```

#### 3. Longhorn Volume Snapshots

**Via Longhorn UI**:

1. Access Longhorn UI
2. Navigate to Volume → Select volume → Take Snapshot
3. Configure recurring snapshots (daily, weekly)
4. Set retention policies

**Backup to S3** (Recommended):

- Configure S3-compatible backup target in Longhorn
- Enable automatic backups for critical volumes
- Store backups off-cluster for disaster recovery

#### 4. Sealed Secrets Key (CRITICAL)

**⚠️ This is the most critical backup — without it, you cannot decrypt
secrets!**

```bash
# Backup the sealing key
kubectl get secret -n kube-system sealed-secrets-key -o yaml > sealed-secrets-key-backup.yaml

# Store securely:
# - Encrypted storage (GPG, age, or similar)
# - Off-site location (different physical location)
# - Access-controlled (limited who can decrypt)
```

**Restoration**:

```bash
# Restore sealed-secrets key to new cluster
kubectl apply -f sealed-secrets-key-backup.yaml

# Restart sealed-secrets controller
kubectl rollout restart deployment -n kube-system sealed-secrets-controller
```

---

## Monitoring

> **Note**: Monitoring stack (Prometheus + Grafana) is currently
> **planned/inactive**. To enable, uncomment `monitoring.yaml` in
> `argocd/infrastructure/kustomization.yaml`.

### Planned Components

**Prometheus**:

- Cluster metrics collection
- Application metrics scraping
- Custom alerting rules
- Long-term retention

**Grafana**:

- Pre-built dashboards for infrastructure
- Application-specific metrics visualization
- Certificate expiration tracking
- Resource utilization monitoring

### Activation Steps

```bash
# 1. Uncomment in kustomization
vim argocd/infrastructure/kustomization.yaml
# Uncomment: - monitoring.yaml

# 2. Commit and push
git commit -am "feat(infrastructure): enable monitoring stack"
git push

# 3. Sync in ArgoCD
# Navigate to ArgoCD UI and sync the infrastructure Application
```

---

## Troubleshooting

### Application Won't Sync

**Symptoms**: Application stuck in "OutOfSync" or sync fails

**Debugging Steps**:

```bash
# 1. Check application status
kubectl get application <app-name> -n argocd -o yaml

# 2. View sync errors in ArgoCD CLI
argocd app get <app-name>

# 3. Test Kustomize build locally
kubectl apply -k apps/<app-name> --dry-run=server

# 4. Check ArgoCD application controller logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller

# 5. Verify Git repository is accessible
argocd repo list
```

**Common Causes**:

- Invalid YAML syntax
- Missing Helm values
- Incorrect namespace references
- Git repository authentication issues

---

### Secret Not Available

**Symptoms**: Pods fail with "secret not found" errors

**Debugging Steps**:

```bash
# 1. Verify SealedSecret exists
kubectl get sealedsecret <secret-name> -n <namespace>

# 2. Check if Secret was unsealed
kubectl get secrets -n <namespace>

# 3. Check sealed-secrets controller logs
kubectl logs -n kube-system -l name=sealed-secrets-controller

# 4. Verify sealed-secrets controller is running
kubectl get pods -n kube-system -l name=sealed-secrets-controller
```

**Common Causes**:

- SealedSecret not committed to Git
- Sealed-secrets controller not running
- Wrong namespace in SealedSecret
- Encryption key mismatch (wrong cluster)

---

### Certificate Issues

**Symptoms**: TLS errors, certificate not issued

**Debugging Steps**:

```bash
# 1. Check certificate status
kubectl get certificates -A

# 2. Describe certificate for events
kubectl describe certificate <cert-name> -n <namespace>

# 3. Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager

# 4. Verify DNS propagation (for DNS01 challenge)
dig _acme-challenge.example.com TXT

# 5. Check Cloudflare API token (if using Cloudflare)
kubectl get secret cloudflare-api-token -n cert-manager -o yaml
```

**Common Causes**:

- DNS not propagated
- Cloudflare API token expired or invalid
- Rate limiting from Let's Encrypt
- Incorrect domain in certificate request

---

### Ingress Not Working

**Symptoms**: Application not accessible via domain, 404 errors

**Debugging Steps**:

```bash
# 1. Check Traefik logs
kubectl logs -n traefik -l app.kubernetes.io/name=traefik

# 2. Verify IngressRoute exists
kubectl get ingressroute -n <namespace>

# 3. Describe IngressRoute for details
kubectl describe ingressroute <name> -n <namespace>

# 4. Check if service exists and has endpoints
kubectl get svc -n <namespace>
kubectl get endpoints -n <namespace>

# 5. Verify Traefik configuration
kubectl get configmap -n traefik

# 6. Test direct service access (port-forward)
kubectl port-forward svc/<service-name> -n <namespace> 8080:80
```

**Common Causes**:

- IngressRoute host mismatch
- Service selector doesn't match pods
- Wrong service port in IngressRoute
- Traefik middleware issues
- DNS not pointing to cluster ingress

---

### Storage Problems

**Symptoms**: PVCs stuck in Pending, pod mount failures

**Debugging Steps**:

```bash
# 1. Check PVC status
kubectl get pvc -n <namespace>

# 2. Describe PVC for events
kubectl describe pvc <pvc-name> -n <namespace>

# 3. Check Longhorn volumes (via Longhorn UI)
# Access: kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80

# 4. Check Longhorn manager logs
kubectl logs -n longhorn-system -l app=longhorn-manager

# 5. Verify storage class exists
kubectl get storageclass
```

**Common Causes**:

- No available storage on nodes
- Longhorn not fully deployed
- Node disk space exhausted
- Incompatible filesystem settings

#### Longhorn + Multipathd Incompatibility (Ubuntu 24.04)

**Symptom**: New volumes fail to format with error: "device apparently in use"

**Root Cause**: Multipathd interferes with Longhorn's iSCSI volumes

**Fix** (apply on all worker nodes):

```bash
# Create multipath configuration
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

# Restart multipathd service
systemctl restart multipathd

# Verify configuration
multipath -ll
```

**Reference**: [Longhorn GitHub Issue
\#1210](https://github.com/longhorn/longhorn/issues/1210#issuecomment-671689746)

---

## Additional Resources

- [ArgoCD Best Practices][argocd-best-practices]
- [Kustomize Documentation](https://kustomize.io/)

[argocd-best-practices]: https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/

- [Traefik Configuration](https://doc.traefik.io/traefik/)
- [Longhorn Documentation](https://longhorn.io/docs/)
- [Sealed Secrets
  Documentation](https://github.com/bitnami-labs/sealed-secrets)

---

**Questions or Issues?** Check the main [README](../README.md) or open an
issue in the repository.
