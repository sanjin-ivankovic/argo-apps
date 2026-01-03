# Folder Naming Conventions - ArgoCD GitOps Best Practices

This document outlines the official folder naming conventions for ArgoCD
GitOps repositories based on ArgoCD best practices and official
documentation.

## Table of Contents

- [Overview](#overview)
- [Core Principles](#core-principles)
- [Directory Naming](#directory-naming)
- [File Naming](#file-naming)
- [Application Naming](#application-naming)
- [Namespace Naming](#namespace-naming)
- [Path Patterns](#path-patterns)
- [Examples from Official Documentation](#examples-from-official-documentation)

---

## Overview

ArgoCD uses directory structure to discover and manage applications. The
naming conventions ensure:

- **Consistency**: Predictable structure across all applications
- **Discoverability**: Easy to find and manage applications
- **Automation**: Works seamlessly with ApplicationSet generators
- **Clarity**: Self-documenting structure

---

## Core Principles

### 1. **Lowercase with Hyphens**

- Use lowercase letters
- Separate words with hyphens (`-`)
- Avoid underscores, spaces, or camelCase
- **Example**: `cluster-addons`, `guestbook`, `home-assistant`

### 2. **Descriptive and Meaningful**

- Names should clearly indicate purpose
- Use full words, not abbreviations (unless standard)
- **Good**: `cert-manager`, `kube-prometheus-stack`
- **Avoid**: `cm`, `kps`, `ha`

### 3. **Consistent Structure**

- Follow the same pattern across all applications
- Directory name typically matches application name
- Directory name typically matches namespace name

### 4. **Kubernetes-Compatible**

- Must be valid Kubernetes resource names
- DNS subdomain format (RFC 1123)
- Max 253 characters (practical limit: 63 for namespaces)
- Alphanumeric and hyphens only

---

## Directory Naming

### Top-Level Directories

**Recommended Structure**:

```text
repo-root/
├── argocd/                    # ArgoCD bootstrap and configuration
├── infrastructure/            # Infrastructure/platform components
├── apps/                       # Application workloads (flat structure)
# Note: Custom Helm charts are in separate repository: https://gitlab.example.com/homelab/helm-charts.git
├── scripts/                   # Utility scripts
└── docs/                      # Documentation
```

**Naming Rules**:

- **Singular form**: `application` not `applications` (but `applications`
  is acceptable for clarity)
- **Lowercase**: All lowercase
- **Descriptive**: Clear purpose

### Platform Components

**Structure**:

```text
infrastructure/
├── argocd/
├── traefik/
│   └── traefik/
├── security/
│   └── cert-manager/
├── networking/
│   ├── metallb/
│   └── external-services/
├── storage/
│   └── longhorn/
└── monitoring/
    └── kube-prometheus-stack/
```

**Naming Convention**:

- **By function**: `ingress`, `security`, `networking`, `storage`,
  `monitoring`
- **Component name**: Use official component name (e.g., `traefik`,
  `cert-manager`)
- **Hyphenated**: Multi-word components use hyphens (`cert-manager`,
  `kube-prometheus-stack`)

### Application Workloads

**Structure**:

```text
apps/
├── affine/                    # Collaborative workspace
├── freshrss/                  # RSS reader
├── home-assistant/            # Home automation
├── it-tools/                  # Developer tools
├── myspeed/                   # Speed test
├── omni-tools/                # Utility tools
├── postgresql/                # Database
├── privatebin/                # Pastebin
├── searxng/                   # Search engine
├── stirling-pdf/              # PDF tools
└── valkey/                    # Cache
```

**Naming Convention**:

- **Flat structure**: All apps in `apps/` directory (no categories)
- **Application name**: Use official application name
- **Hyphenated**: Multi-word names use hyphens (`stirling-pdf`,
  `home-assistant`)
- **Auto-discovered**: Applications automatically discovered by Git directory
  generator

### Base/Overlay Pattern

**Structure**:

```text
infrastructure/{component}/
├── base/                      # Base configuration
│   ├── kustomization.yaml
│   └── values.yaml
└── overlays/                  # Environment-specific
    ├── dev/
    ├── staging/
    └── prod/
```

**Naming Convention**:

- **`base/`**: Always named `base` (lowercase)
- **`overlays/`**: Always named `overlays` (lowercase, plural)
- **Environment names**: Short, lowercase (`dev`, `staging`, `prod`, `test`)

---

## File Naming

### Standard Files

**Required Files**:

- `kustomization.yaml` - Kustomize configuration (lowercase, exact name)
- `values.yaml` - Helm values (lowercase, exact name)
- `README.md` - Documentation (uppercase, exact name)

**Naming Rules**:

- **YAML files**: Lowercase with hyphens (`ingressroute.yaml`, `configmap.yaml`)
- **Markdown files**: Uppercase for standard files (`README.md`, `CHANGELOG.md`)
- **Scripts**: Lowercase or Go binaries (`kryptos`, utility scripts)

### Application Files

**Structure**:

```text
apps/<app-name>/
├── kustomization.yaml         # Root kustomization (required)
├── values.yaml                # Helm values (if applicable)
├── base/                      # Base manifests (if manifest-based)
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml
├── ingress/
│   ├── ingressroute.yaml
│   └── kustomization.yaml
├── secrets/
│   └── kustomization.yaml
└── jobs/
    └── kustomization.yaml
```

**Naming Convention**:

- **Subdirectories**: Lowercase, descriptive (`ingress`, `secrets`, `jobs`,
  `base`)
- **Manifest files**: Standard Kubernetes resource names (`deployment.yaml`,
  `service.yaml`)
- **Ingress files**: Component-specific (`ingressroute.yaml` for Traefik)

---

## Application Naming

### Application Resource Names

**Convention**: Match directory name

**Example**:

```text
# Directory: apps/postgresql/
# Application name: postgresql
metadata:
  name: postgresql
```

**Rules**:

- **Lowercase**: All lowercase
- **Hyphens**: Use hyphens for multi-word names
- **Consistent**: Application name = Directory name = Namespace name (typically)

### ApplicationSet Template

**Pattern**: Use `{{.path.basename}}` to extract directory name

**Example**:

```text
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
spec:
  generators:
    - git:
        directories:
          - path: apps/*
  template:
    metadata:
      name: "{{.path.basename}}" # Extracts directory name
    spec:
      destination:
        namespace: "{{.path.basename}}" # Same as application name
```

**Result**:

- Directory: `apps/postgresql/` → Application: `postgresql`
- Directory: `apps/home-assistant/` → Application: `home-assistant`

---

## Namespace Naming

### Convention

**Rule**: Namespace typically matches application name

**Examples**:

- Application: `postgresql` → Namespace: `postgresql`
- Application: `home-assistant` → Namespace: `home-assistant`
- Application: `kube-prometheus-stack` → Namespace: `monitoring` (may differ
  for clarity)

### Kubernetes Constraints

**RFC 1123 DNS Subdomain**:

- Lowercase alphanumeric characters or hyphens
- Must start and end with alphanumeric
- Max 63 characters
- **Valid**: `postgresql`, `home-assistant`, `kube-prometheus-stack`
- **Invalid**: `PostgreSQL`, `home_assistant`, `kube.prometheus.stack`

---

## Path Patterns

### Git Generator Patterns

**Common Patterns**:

```text
# Single level
directories:
  - path: apps/*

# Flat structure (current)
directories:
  - path: apps/*

# Exclude patterns (if needed)
directories:
  - path: apps/*
    exclude: true
```

### Path Variables

**Available Variables**:

- `{{.path.path}}` - Full path (e.g., `apps/postgresql`)
- `{{.path.basename}}` - Directory name (e.g., `postgresql`)
- `{{.path[0]}}` - First path segment (e.g., `apps`)
- `{{.path.basename}}` - Directory name (used for namespace)

**Example Usage**:

```text
template:
  metadata:
    name: "{{.path.basename}}"
  spec:
    source:
      path: "{{.path.path}}"
    destination:
      namespace: "{{.path.basename}}"
```

---

## Examples from Official Documentation

### Example 1: Cluster Addons

**Official Pattern**:

```text
applicationset/examples/git-generator-directory/cluster-addons/
├── guestbook/
├── helm-guestbook/
└── kustomize-guestbook/
```

**Naming**:

- Top-level: `cluster-addons` (descriptive, hyphenated)
- Applications: `guestbook`, `helm-guestbook`, `kustomize-guestbook`
  (lowercase, hyphenated)

### Example 2: Multi-Environment

**Pattern**:

```text
apps/
├── core/
│   └── postgresql/
│       ├── base/
│       └── overlays/
│           ├── dev/
│           ├── staging/
│           └── prod/
```

**Naming**:

- Application: `postgresql` (lowercase, official name)
- Base: `base` (lowercase, standard)
- Environments: `dev`, `staging`, `prod` (lowercase, short)

### Example 3: Platform Components

**Pattern**:

```text
infrastructure/
├── traefik/
│   ├── kustomization.yaml
│   └── values.yaml
└── cert-manager/
    ├── kustomization.yaml
    └── values.yaml
```

**Naming**:

- Directory: `traefik`, `cert-manager` (lowercase, official name,
  hyphenated)
- Component: Use official component names directly

---

## Best Practices Summary

### ✅ DO

1. **Use lowercase with hyphens**: `home-assistant`, `cert-manager`
2. **Match directory to application name**: `apps/postgresql/` → app:
   `postgresql`
3. **Use flat structure**: All apps in `apps/` directory (no categories)
4. **Follow official component names**: `traefik`, `cert-manager`,
   `kube-prometheus-stack`
5. **Use standard subdirectories**: `base/`, `overlays/`, `ingress/`,
   `secrets/`
6. **Keep names short but clear**: `dev` not `development`, `prod` not
   `production`

### ❌ DON'T

1. **Don't use underscores**: `home_assistant` ❌
2. **Don't use camelCase**: `homeAssistant` ❌
3. **Don't use spaces**: `home assistant` ❌
4. **Don't use uppercase**: `PostgreSQL` ❌ (use `postgresql`)
5. **Don't abbreviate unnecessarily**: `cm` ❌ (use `cert-manager`)
6. **Don't mix naming styles**: Be consistent across all directories

---

## Validation

### Kubernetes Name Validation

**Check if name is valid**:

```bash
# Must match RFC 1123 DNS subdomain
# - Lowercase alphanumeric or hyphens
# - Must start and end with alphanumeric
# - Max 63 characters for namespaces
```

**Examples**:

- ✅ `postgresql` - Valid
- ✅ `home-assistant` - Valid
- ✅ `kube-prometheus-stack` - Valid
- ❌ `PostgreSQL` - Invalid (uppercase)
- ❌ `home_assistant` - Invalid (underscore)
- ❌ `home assistant` - Invalid (space)
- ❌ `-postgresql` - Invalid (starts with hyphen)

### Directory Name Validation

**Check consistency**:

```bash
# Application name should match directory name
# Namespace should typically match application name
```

**Example Validation**:

```text
# Directory: apps/postgresql/
# Application name: postgresql ✅
# Namespace: postgresql ✅
```

---

## Migration Checklist

When renaming directories/applications:

- [ ] Update directory name (lowercase, hyphens)
- [ ] Update Application resource name
- [ ] Update namespace (if changed)
- [ ] Update ApplicationSet generator paths
- [ ] Update all references in manifests
- [ ] Update documentation
- [ ] Verify Kubernetes name validation
- [ ] Test ApplicationSet generation
- [ ] Update CI/CD pipelines if needed

---

## Related Documentation

- [ArgoCD Best Practices][argocd-best-practices]
- [ApplicationSet Git Generator][appset-git-generator]
- [Kubernetes Naming Conventions][k8s-naming]
- [RFC 1123 - DNS Subdomain Names](https://tools.ietf.org/html/rfc1123)

[argocd-best-practices]: https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/
[appset-git-generator]: https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Git
[k8s-naming]: https://kubernetes.io/docs/concepts/overview/working-with-objects/names/

---

## Quick Reference

| Element         | Convention             | Example              |
| --------------- | ---------------------- | -------------------- |
| **Top-level**   | lowercase, descriptive | `applications`       |
| **Category**    | lowercase, singular    | `core`               |
| **App dirs**    | lowercase, hyphens     | `postgresql`         |
| **Base dir**    | `base` (exact)         | `base/`              |
| **Overlays**    | `overlays` (exact)     | `overlays/`          |
| **Environment** | lowercase, short       | `dev`, `staging`     |
| **Subdirs**     | lowercase, descriptive | `ingress`, `secrets` |
| **YAML files**  | lowercase, hyphens     | `kustomization.yaml` |
| **App names**   | lowercase, hyphens     | `postgresql`         |
| **Namespaces**  | lowercase, hyphens     | `postgresql`         |

---

## See Also

- [REPOSITORY_STRUCTURE.md](./REPOSITORY_STRUCTURE.md) - Complete repository
  structure guide
- [APPLICATION_DEVELOPMENT.md](./APPLICATION_DEVELOPMENT.md) - How to add
  applications
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Architecture overview
