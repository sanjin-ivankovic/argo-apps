# Application Development Guide

## Table of Contents

- [Overview](#overview)
- [Application Patterns](#application-patterns)
- [Adding a Helm-Based Application](#adding-a-helm-based-application)
- [Adding a Manifest-Based Application](#adding-a-manifest-based-application)
- [ApplicationSet Configuration](#applicationset-configuration)
- [Ingress Configuration](#ingress-configuration)
- [Secret Management](#secret-management)
- [Testing Applications](#testing-applications)
- [Application Lifecycle](#application-lifecycle)
- [Best Practices](#best-practices)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Related Documentation](#related-documentation)

---

## Overview

This guide explains how to add, configure, and manage applications in this
GitOps repository. Applications use a flat structure in the `apps/`
directory and can be deployed using either Helm charts or raw Kubernetes
manifests.

### Key Concepts

- **Root Kustomization**: Every application must have a root
  `kustomization.yaml` at the application directory level
- **ApplicationSet**: All applications are managed via ArgoCD ApplicationSet
  in `argocd/applications/apps-set.yaml`
- **Auto-Discovery**: Applications are automatically discovered via Git
  directory generator - no manual configuration needed
- **Flat Structure**: All applications are in `apps/` directory (no categories)
- **Manual Sync**: ArgoCD sync is manual (intentional for safety)

### Quick Decision Tree

```text
New Application?
├── Has Helm Chart Available?
│   ├── Yes → Use Helm-Based Pattern
│   │   ├── Custom chart?
│   │   │   → Use oci://registry.example.com/homelab/helm-charts/<chart-name>
│   │   └── Public chart?
│   │       → Use standard Helm repository
│   └── No → Use Manifest-Based Pattern
└── Create Directory
    └── apps/<app-name>/
        → Auto-discovered by ApplicationSet!
```

---

## Application Patterns

This repository supports two application deployment patterns:

### Pattern 1: Helm-Based Applications

**Use when**: Application has an official Helm chart available

**Characteristics**:

- Uses Helm chart from a repository
- Chart version is **always pinned**
- Values overridden via `values.yaml`
- Additional resources (ingress, secrets) via Kustomize

**Example Applications**: PostgreSQL, Home Assistant, Valkey, Stirling PDF

### Pattern 2: Manifest-Based Applications

**Use when**: No Helm chart available or custom deployment needed

**Characteristics**:

- Raw Kubernetes manifests in `base/` directory
- Full control over deployment configuration
- Uses Kustomize for resource composition

**Example Applications**: IT Tools, Affine, SearXNG, MySpeed, Omni Tools

---

## Adding a Helm-Based Application

### Step 1: Create Application Directory

Create the directory structure in `apps/`:

```bash
# Example: Adding a new app
mkdir -p apps/my-app/{ingress,secrets,jobs}
cd apps/my-app
```

**Note**: Applications are automatically discovered by the Git directory
generator - no manual ApplicationSet editing needed!

### Step 2: Create Root Kustomization

Create `kustomization.yaml` at the application root:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

helmCharts:
  - name: my-app
    repo: https://charts.example.com/stable
    version: 1.2.3 # Always pin version!
    releaseName: my-app
    namespace: my-app
    valuesFile: values.yaml

resources:
  - ingress
  - secrets # If secrets are needed
  - jobs # If jobs are needed (optional)
```

**Key Points**:

- `namespace` must match application name (except special cases like Rancher)
- `version` must be pinned (never use `latest`)
- `valuesFile` references `values.yaml` in the same directory
- `resources` includes additional directories (ingress, secrets, jobs)

### Step 3: Create Helm Values File

Create `values.yaml` with application-specific configuration:

```text
# Example values.yaml
image:
  registry: docker.io
  repository: myapp/myapp
  tag: "1.2.3"

replicaCount: 1

service:
  type: ClusterIP
  port: 80

persistence:
  enabled: true
  storageClass: longhorn
  size: 10Gi

resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "200m"

nodeSelector:
  node-role.kubernetes.io/worker: worker
```

**Best Practices**:

- Use `longhorn` as storage class
- Set appropriate resource limits
- Use node selectors for worker nodes
- Reference secrets via `existingSecret` when possible

### Step 4: Create Ingress Configuration

Create `ingress/ingressroute.yaml`:

```text
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: my-app-ingressroute
  namespace: my-app
spec:
  entryPoints:
    - websecure # HTTPS only
  routes:
    - kind: Rule
      match: Host(`my-app.example.com`)
      services:
        - kind: Service
          name: my-app # Must match Helm release name
          port: 80
  tls:
    certResolver: letsencrypt-prod
```

Create `ingress/kustomization.yaml`:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

resources:
  - ingressroute.yaml
```

**Key Points**:

- Use `websecure` entry point for HTTPS
- Service name must match Helm release name
- Use `letsencrypt-prod` cert resolver
- Domain should follow pattern: `<app-name>.example.com`

### Step 5: Create Secrets (If Needed)

If the application requires secrets:

1. **Create kryptos configuration**:

   ```text
   # scripts/kryptos/configs/my-app.yaml
   app_name: "my-app"
   display_name: "My App"
   namespace: "my-app"

   secrets:
     - name: "my-app-admin"
       display_name: "Admin Secret"
       type: "Opaque"
       keys: ["username", "password"]
       description: "Administrator credentials for My App"
   ```

2. **Generate sealed secrets**:

   ```bash
   cd scripts/kryptos
   ./kryptos
   # Select my-app from the interactive menu
   # Enter values or use auto-generation keywords:
   #   - secure: 32-char secure password
   #   - strong: 32-char with symbols
   #   - apikey: 64-char hex key
   #   - passphrase: 4-word passphrase
   ```

3. **Create secrets kustomization**:

   ```text
   # secrets/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization

   namespace: my-app

   resources:
     - my-app-admin-secret.yaml
   ```

### Step 6: Commit and Sync

**Note**: No ApplicationSet editing needed! The Git directory generator
automatically discovers apps in `apps/`.

### Step 7: Commit and Push

```bash
# Commit changes
git add apps/my-app
git commit -m "Add my-app application"
git push origin main

# Sync ApplicationSet in ArgoCD UI - my-app will appear automatically!
# Then manually sync the my-app application
argocd app sync my-app
```

---

## Adding a Manifest-Based Application

### Step 1: Create Manifest Application Directory

```bash
mkdir -p apps/my-app/{base,ingress,secrets}
cd apps/my-app
```

### Step 2: Create Manifest Root Kustomization

Create `kustomization.yaml`:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

resources:
  - base
  - ingress
  - secrets # If needed
```

### Step 3: Create Base Manifests

Create `base/deployment.yaml`:

```text
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        - name: my-app
          image: myapp/myapp:1.2.3
          ports:
            - containerPort: 80
          env:
            - name: ENV_VAR
              value: "value"
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "200m"
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: my-app-data
      nodeSelector:
        node-role.kubernetes.io/worker: worker
```

Create `base/service.yaml`:

```text
apiVersion: v1
kind: Service
metadata:
  name: my-app
  namespace: my-app
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 80
      protocol: TCP
  selector:
    app: my-app
```

Create `base/pvc.yaml` (if persistent storage needed):

```text
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-app-data
  namespace: my-app
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: 10Gi
```

Create `base/kustomization.yaml`:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

resources:
  - deployment.yaml
  - service.yaml
  - pvc.yaml # If needed
```

### Step 4: Configure Manifest Application Ingress

Same as Helm-based application (see [Ingress
Configuration](#ingress-configuration)).

### Step 5: Configure Manifest Application Secrets

Same as Helm-based application (see [Secret Management](#secret-management)).

### Step 6: Add to ApplicationSet

Same as Helm-based application (see [ApplicationSet
Configuration](#applicationset-configuration)).

### Step 7: Commit and Sync

Same as Helm-based application.

---

## ApplicationSet Configuration

All applications are **automatically discovered** via ArgoCD ApplicationSet
using a **Git directory generator** in `argocd/applications/apps-set.yaml`.

### Structure

```text
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: apps
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: ssh://git@gitlab.example.com:2424/homelab/argo-apps.git
        revision: main
        directories:
          - path: apps/* # Auto-discovers all subdirectories!
  template:
    metadata:
      name: "{{path.basename}}"
    spec:
      project: default
      source:
        repoURL: ssh://git@gitlab.example.com:2424/homelab/argo-apps.git
        targetRevision: main
        path: "{{path.path}}"
      destination:
        server: https://kubernetes.default.svc
        namespace: "{{path.basename}}" # Namespace = directory name
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
```

### Adding an Application

**No ApplicationSet editing required!** Simply create a directory in `apps/`
and it will be automatically discovered:

```bash
mkdir -p apps/my-app
# Add kustomization.yaml and other resources
git add apps/my-app
git commit -m "Add my-app"
git push
# Sync the ApplicationSet in ArgoCD UI
# my-app will appear automatically!
```

### Namespace Rules

- **Default**: App name = namespace name
- **Exception**: Rancher uses `cattle-system` namespace
- **Consistency**: Always use lowercase, hyphen-separated names

### Path Format

- **Format**: `apps/<app-name>`
- **Structure**: Flat structure in `apps/` directory (no categories)
- **Example**: `apps/it-tools`

---

## Ingress Configuration

All applications use **Traefik IngressRoute** for ingress.

### Basic IngressRoute

```text
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: my-app-ingressroute
  namespace: my-app
spec:
  entryPoints:
    - websecure # HTTPS only
  routes:
    - kind: Rule
      match: Host(`my-app.example.com`)
      services:
        - kind: Service
          name: my-app
          port: 80
  tls:
    certResolver: letsencrypt-prod
```

### Entry Points

- **`web`**: HTTP (port 80) - rarely used
- **`websecure`**: HTTPS (port 443) - **recommended**

### Certificate Resolvers

- **`letsencrypt-prod`**: Production certificates (recommended)
- **`letsencrypt-staging`**: Staging certificates (for testing)

### Domain Naming

- **Pattern**: `<app-name>.example.com`
- **Examples**:
  - `affine.example.com`
  - `home.example.com`
  - `it-tools.example.com`

### Advanced Routing

For complex routing needs:

```text
spec:
  entryPoints:
    - websecure
  routes:
    - kind: Rule
      match: Host(`my-app.example.com`) && PathPrefix(`/api`)
      services:
        - name: my-app-api
          port: 8080
    - kind: Rule
      match: Host(`my-app.example.com`)
      services:
        - name: my-app
          port: 80
  tls:
    certResolver: letsencrypt-prod
```

### Middleware (Optional)

For authentication, rate limiting, etc.:

```text
spec:
  routes:
    - kind: Rule
      match: Host(`my-app.example.com`)
      middlewares:
        - name: auth-middleware
      services:
        - name: my-app
          port: 80
```

---

## Secret Management

Secrets are managed using **Sealed Secrets** to enable Git-safe secret storage.

### Workflow

1. **Create configuration**: `scripts/kryptos/configs/{app}.yaml`
2. **Generate sealed secrets**: `cd scripts/kryptos && ./kryptos`
3. **Commit sealed secrets**: SealedSecrets are encrypted and Git-safe
4. **Controller unseals**: Sealed Secrets Controller automatically creates
   Kubernetes secrets

### Creating Secret Configuration

1. **Create configuration file**:

   ```text
   # scripts/kryptos/configs/my-app.yaml
   app_name: "my-app"
   display_name: "My Application"
   namespace: "my-app"

   secrets:
     - name: "my-app-admin"
       display_name: "Admin Credentials"
       type: "Opaque"
       keys: ["username", "password"]
       description: "Administrator credentials"
   ```

2. **Run kryptos interactive tool**:

   ```bash
   cd scripts/kryptos
   ./kryptos
   # Select my-app from menu
   # Follow prompts to enter values or use auto-generation
   ```

3. **Generated files**: SealedSecret YAML created in `apps/my-app/secrets/`

### Secret Types

The script supports multiple secret types:

- **Admin secrets**: User credentials
- **Database secrets**: Database connection info
- **API secrets**: API keys and tokens
- **Custom secrets**: Application-specific secrets

### Password Generation Options

1. **Manual Entry**: Type your own password
2. **Secure Password**: 32 chars, alphanumeric
3. **Strong Password**: 32 chars with symbols
4. **Passphrase**: 4 memorable words with number
5. **API Key**: 64 chars alphanumeric

### Using Secrets in Applications

**Helm-based** (via values.yaml):

```text
auth:
  existingSecret: "my-app-admin-secret"
  secretKeys:
    adminPasswordKey: password
```

**Manifest-based** (via env):

```text
env:
  - name: PASSWORD
    valueFrom:
      secretKeyRef:
        name: my-app-admin-secret
        key: password
```

### Secret Kustomization

Create `secrets/kustomization.yaml`:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

resources:
  - my-app-admin-secret.yaml
  - my-app-db-secret.yaml
```

---

## Testing Applications

### Local Testing with Kustomize

Test kustomization locally:

```bash
# Build kustomization
kubectl kustomize apps/my-app

# Validate YAML
kubectl kustomize apps/my-app | kubectl apply --dry-run=client -f -
```

### Local Testing with Helm

For Helm-based apps:

```bash
# Template Helm chart
helm template my-app oci://registry.example.com/homelab/helm-charts/my-app -f apps/my-app/values.yaml

# Validate
helm template my-app oci://registry.example.com/homelab/helm-charts/my-app -f apps/my-app/values.yaml | kubectl apply --dry-run=client -f -
```

### ArgoCD Validation

1. **Check application status**:

   ```bash
   argocd app get my-app
   ```

2. **View manifests**:

   ```bash
   argocd app manifests my-app
   ```

3. **Diff**:

   ```bash
   argocd app diff my-app
   ```

### Pre-Sync Checklist

- [ ] Root `kustomization.yaml` exists
- [ ] Application added to ApplicationSet
- [ ] IngressRoute configured correctly
- [ ] Secrets created and sealed (if needed)
- [ ] Resource limits set appropriately
- [ ] Storage class set to `longhorn` (if needed)
- [ ] Node selectors configured (if needed)
- [ ] Local kustomization validates
- [ ] ArgoCD diff shows expected changes

---

## Application Lifecycle

### Application Addition Workflow

1. Create directory structure
2. Create manifests/values
3. Configure ingress
4. Create secrets (if needed)
5. Add to ApplicationSet
6. Commit and push
7. Sync in ArgoCD

### Updating an Application

**Helm-based**:

1. Update `values.yaml`
2. Update chart version in `kustomization.yaml` (if needed)
3. Commit and push
4. Sync in ArgoCD

**Manifest-based**:

1. Update manifests in `base/`
2. Commit and push
3. Sync in ArgoCD

### Upgrading Helm Charts

1. **Check available versions**:

   ```bash
   helm search repo <chart-name> --versions
   ```

2. **Update version** in `kustomization.yaml`:

   ```text
   helmCharts:
     - name: my-app
       version: 1.3.0 # Update version
   ```

3. **Review breaking changes** in chart changelog

4. **Update values.yaml** if needed

5. **Commit and sync**

### Removing an Application

1. **Remove from ApplicationSet**:
   - No editing needed - just delete the directory
   - Git directory generator will automatically remove it from discovery

2. **Delete application directory** (optional):

   ```bash
   rm -rf apps/my-app
   ```

3. **Commit and push**

4. **Delete in ArgoCD** (or let ApplicationSet handle it):

   ```bash
   argocd app delete my-app
   ```

5. **Clean up resources** (if needed):
   - Delete PVCs
   - Delete secrets
   - Delete namespaces

---

## Best Practices

### Directory Structure

- **Consistent**: Follow established patterns
- **Organized**: Use appropriate categories
- **Clean**: Remove unused files

### Naming Conventions

- **Application names**: Lowercase, hyphen-separated (`my-app`)
- **Namespace**: Match application name (except special cases)
- **Resources**: Use consistent naming (`{app-name}-{resource-type}`)

### Version Management

- **Helm charts**: Always pin versions (never use `latest`)
- **Container images**: Pin tags or use digests
- **Documentation**: Document version choices

### Resource Management

- **Limits**: Always set resource limits
- **Requests**: Set appropriate requests
- **Storage**: Use `longhorn` storage class
- **Node selectors**: Use for worker nodes

### Security

- **Secrets**: Always use Sealed Secrets
- **RBAC**: Follow principle of least privilege
- **Images**: Use trusted image sources
- **Networking**: Use HTTPS (websecure)

### Git Workflow

- **Commits**: Meaningful commit messages
- **Branches**: Use feature branches for major changes
- **Testing**: Test locally before committing
- **Documentation**: Update docs with changes

### ArgoCD Sync

- **Manual sync**: Always use manual sync (safety)
- **Review**: Review changes before syncing
- **Monitor**: Monitor sync status
- **Rollback**: Know how to rollback if needed

---

## Examples

### Example 1: Simple Helm-Based App

**Structure**:

```text
apps/my-app/
├── kustomization.yaml
├── values.yaml
├── ingress/
│   ├── ingressroute.yaml
│   └── kustomization.yaml
└── secrets/
    ├── my-app-admin-secret.yaml
    └── kustomization.yaml
```

**Root kustomization.yaml**:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

helmCharts:
  - name: my-app
    repo: https://charts.example.com/stable
    version: 1.2.3
    releaseName: my-app
    namespace: my-app
    valuesFile: values.yaml

resources:
  - ingress
  - secrets
```

### Example 2: Complex Manifest-Based App

**Structure**:

```text
apps/my-app/
├── kustomization.yaml
├── base/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── pvc.yaml
│   └── kustomization.yaml
├── ingress/
│   ├── ingressroute.yaml
│   └── kustomization.yaml
└── secrets/
    ├── my-app-admin-secret.yaml
    ├── my-app-db-secret.yaml
    └── kustomization.yaml
```

**Root kustomization.yaml**:

```text
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-app

resources:
  - base
  - ingress
  - secrets
```

### Example 3: App with Database Dependency

For apps requiring PostgreSQL:

1. **Create database secret** (in PostgreSQL app):

   ```bash
   cd scripts/kryptos && ./kryptos
   # Select PostgreSQL and create database secret for the app
   ```

2. **Reference in app values.yaml**:

   ```text
   database:
     host: postgresql
     name: my-app-db
     existingSecret: my-app-db-secret
   ```

3. **Create database job** (in PostgreSQL app):
   - See `apps/postgresql/jobs/` for examples
   - Use sync waves for ordering

---

## Troubleshooting

### Application Not Appearing in ArgoCD

**Check**:

- Application added to ApplicationSet?
- Path correct in ApplicationSet?
- Namespace matches?
- Root kustomization.yaml exists?

**Fix**:

```bash
# Verify ApplicationSet
kubectl get applicationset apps-set -n argocd -o yaml

# Check ArgoCD logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

### Sync Failing

**Check**:

- Kustomization valid?
- Helm chart accessible?
- Secrets exist?
- Resource limits appropriate?

**Fix**:

```bash
# Validate kustomization
kubectl kustomize apps/my-app

# Check ArgoCD app details
argocd app get my-app

# View sync logs
argocd app logs my-app
```

### Ingress Not Working

**Check**:

- IngressRoute created?
- Service name matches?
- Domain DNS configured?
- Certificate issued?

**Fix**:

```bash
# Check IngressRoute
kubectl get ingressroute -n my-app

# Check Traefik logs
kubectl logs -n traefik -l app.kubernetes.io/name=traefik

# Check certificates
kubectl get certificates -n my-app
```

### Secrets Not Unsealing

**Check**:

- Sealed Secrets Controller running?
- SealedSecret created?
- Controller has access?

**Fix**:

```bash
# Check controller
kubectl get pods -n kube-system | grep sealed-secrets

# Check SealedSecret
kubectl get sealedsecret -n my-app

# Check unsealed secret
kubectl get secret -n my-app
```

---

## Related Documentation

- [Architecture Documentation](./ARCHITECTURE.md) - System architecture overview
- [Platform Components](./PLATFORM_COMPONENTS.md) - Platform component details
- [Troubleshooting](./TROUBLESHOOTING.md) - Common issues and solutions
- [Security](./SECURITY.md) - Security best practices
- [Main README](../README.md) - Repository overview

---

## See Also

- [ArgoCD ApplicationSet Documentation][argocd-appset]
- [Kustomize Documentation](https://kustomize.io/)
- [Helm Documentation](https://helm.sh/docs/)
- [Traefik IngressRoute Documentation][traefik-ingressroute]

[argocd-appset]: https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/
[traefik-ingressroute]: https://doc.traefik.io/traefik/routing/providers/kubernetes-crd/
