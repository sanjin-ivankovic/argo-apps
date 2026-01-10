# Renovate Configuration Guide

**Repository**: argo-apps
**Last Updated**: 2026-01-03

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration Structure](#configuration-structure)
3. [Enabled Managers](#enabled-managers)
4. [Custom Regex Managers](#custom-regex-managers)
5. [Package Rules](#package-rules)
6. [Adding New Rules](#adding-new-rules)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Overview

This repository uses [Renovate](https://docs.renovatebot.com/) to automatically
track and update dependencies across the homelab Kubernetes cluster. The
configuration is designed for a **GitOps workflow** with ArgoCD, where:

- Updates are proposed via merge requests (MRs)
- Manual review and approval required before merging
- Manual ArgoCD sync required after merging
- Conservative update strategy with stabilization periods

### Key Principles

1. **Safety First**: Critical infrastructure has longer stabilization periods
   (7-14 days)
2. **Manual Control**: Auto-merge is disabled; all updates require review
3. **Grouped Updates**: Related updates are grouped to reduce PR noise
4. **Priority-Based**: Security updates get highest priority (100), breaking
   changes lowest (-10)

---

## Configuration Structure

The main configuration file is
[`renovate.json`](file:///home/user/Projects/private/argo-apps/renovate.json)
with the following sections:

```json
{
  "extends": [...],              // Base presets
  "enabledManagers": [...],      // Which managers to use
  "customManagers": [...],       // Custom regex patterns
  "hostRules": [...],            // Authentication for private registries
  "packageRules": [...],         // Update policies per dependency type
  "vulnerabilityAlerts": {...}   // Security vulnerability handling
}
```

### Base Configuration

- **Timezone**: `Europe/Berlin`
- **Schedule**: `at any time` (runs on schedule, not time-restricted)
- **Semantic Commits**: Enabled with `chore(deps):` prefix
- **Auto-merge**: Disabled (manual approval required)
- **Concurrent Limits**: 10 PRs max, no hourly limit

---

## Enabled Managers

The following managers are enabled to detect different dependency types:

<!-- markdownlint-disable MD013 -->

| Manager          | Purpose                         | Files Detected              |
| ---------------- | ------------------------------- | --------------------------- |
| **argocd**       | ArgoCD Application manifests    | `argocd/**/*.yaml`          |
| **custom.regex** | Custom version extraction       | Various (via patterns)      |
| **dockerfile**   | Dockerfile base images          | `**/Dockerfile`             |
| **gitlabci**     | GitLab CI Docker images         | `.gitlab-ci.yml`            |
| **gomod**        | Go module dependencies          | `go.mod`                    |
| **helm-values**  | Container images in Helm values | `values.yaml`               |
| **kubernetes**   | Kubernetes manifests            | `*.yaml` with k8s resources |
| **kustomize**    | Helm charts in kustomization    | `kustomization.yaml`        |

<!-- markdownlint-enable MD013 -->

### Removed Managers

- ~~`docker-compose`~~ - Not used in this repository
- ~~`gitlabci-include`~~ - Not used in this repository

---

## Custom Regex Managers

We use 4 custom regex managers for special cases:

### 1. GitLab CI Tool Versions

**Purpose**: Extract tool versions from `.gitlab-ci.yml` using Renovate
annotations

**Pattern**:

```text
# renovate: datasource=docker depName=renovate/renovate
RENOVATE_VERSION: "42.65"
```

**Configuration**:

- File pattern: `.gitlab-ci.yml`
- Captures: datasource, depName, versioning, extractVersion, currentValue
- Versioning: Auto-detects (docker for docker datasource, semver
  otherwise)

### 2. Dockerfile ARG Variables

**Purpose**: Extract tool versions from Dockerfile ARG statements with
annotations

**Pattern**:

```text
# renovate: datasource=github-releases depName=helm/helm
ARG HELM_VERSION=3.19.4
```

**Configuration**:

- File pattern: Files ending in `Dockerfile`
- Captures: datasource, depName, versioning, extractVersion,
  currentValue
- Versioning: Defaults to semver

### 3. GitHub Release Download URLs

**Purpose**: Extract versions from GitHub release download URLs in Kustomize
resources

**Pattern**:

```text
resources:
  - https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.34.0/controller.yaml
```

**Configuration**:

- File pattern: `kustomization.yaml` files
- Captures: depName (org/repo), currentValue (version)
- Datasource: github-releases

### 4. Raw GitHub URLs

**Purpose**: Extract versions from raw GitHub content URLs (e.g., ArgoCD
manifests)

**Pattern**:

```text
resources:
  - https://raw.githubusercontent.com/argoproj/argo-cd/v3.2.3/manifests/install.yaml
```

**Configuration**:

- File pattern: `kustomization.yaml` files
- Captures: depName (org/repo), currentValue (version)
- Datasource: github-tags

---

## Package Rules

Package rules define how different types of dependencies are updated. Rules
are applied in order, with later rules overriding earlier ones.

### Rule Priority System

| Priority | Category                 | Example             |
| -------- | ------------------------ | ------------------- |
| 100      | Security vulnerabilities | CVE fixes           |
| 50       | ArgoCD self-update       | GitOps controller   |
| 40       | Longhorn                 | Storage system      |
| 30       | Traefik                  | Ingress controller  |
| 25       | Cert-Manager             | TLS automation      |
| 20       | PostgreSQL               | Shared database     |
| 18       | ArgoCD manifests         | GitOps configs      |
| 15       | Valkey                   | Cache service       |
| 12       | Infrastructure Helm      | General infra       |
| 10       | Monitoring               | Observability       |
| 8        | CI/CD tools              | Pipeline deps       |
| 5        | App Helm charts          | Application updates |
| 3        | App patches              | Low-risk updates    |
| 0        | Docker images            | Container updates   |
| -10      | Major updates            | Breaking changes    |

### Critical Infrastructure Rules

#### ArgoCD (Priority: 50)

- **Files**: `infrastructure/argocd/**/*.yaml`
- **Stabilization**: 14 days
- **Rationale**: Self-managing component; failures affect entire cluster
- **Grouping**: `argocd-self-update`

#### Longhorn (Priority: 40)

- **Files**: `infrastructure/longhorn/**/*.yaml`
- **Stabilization**: 14 days
- **Rationale**: Storage system; protects persistent data
- **Grouping**: `longhorn-updates`

#### Traefik (Priority: 30)

- **Files**: `infrastructure/traefik/**/*.yaml`
- **Stabilization**: 7 days
- **Rationale**: Ingress controller; affects all application access
- **Grouping**: `traefik-updates`

#### Cert-Manager (Priority: 25)

- **Files**: `infrastructure/cert-manager/**/*.yaml`
- **Stabilization**: 7 days
- **Rationale**: TLS certificate automation; security component
- **Grouping**: `cert-manager-updates`

### Application Rules

#### Helm Charts - Minor/Major (Priority: 5)

- **Files**: `apps/*/kustomization.yaml`
- **Update Types**: minor, major
- **Stabilization**: 3 days
- **Grouping**: `{{parentDir}}-helm-charts` (e.g., `affine-helm-charts`)

#### Helm Charts - Patches (Priority: 3)

- **Files**: `apps/*/kustomization.yaml`
- **Update Types**: patch
- **Stabilization**: 3 days
- **Grouping**: `apps-patch-updates` (all patches together)
- **Exclusions**: postgresql, valkey (have dedicated rules)

### Special Rules

#### Private Registry Exclusion

- **Pattern**: `/^registry\.example\.net//`
- **Status**: Disabled
- **Rationale**: Private OCI Helm charts are managed in separate
  `helm-charts` repository

#### Major Updates

- **Priority**: -10 (lowest)
- **Stabilization**: 30 days
- **Rationale**: Breaking changes need extensive testing
- **Exclusions**: CI/CD tools (faster updates acceptable)

---

## Adding New Rules

### Step 1: Identify the Dependency Type

Determine which manager will detect the dependency:

- Helm chart in kustomization? → `kustomize` manager
- Container image in values.yaml? → `helm-values` manager
- Tool version with annotation? → `custom.regex` manager

### Step 2: Choose Rule Placement

Add the rule to `packageRules` array in priority order:

- Critical infrastructure: Priority 20-50
- Applications: Priority 0-15
- Breaking changes: Priority -10

### Step 3: Define the Rule

```json
{
  "description": "Brief description of what this rule does",
  "matchFileNames": ["path/to/files/**/*.yaml"],
  "matchManagers": ["kustomize"],
  "matchDatasources": ["helm"],
  "matchPackageNames": ["/package-pattern/"],
  "matchUpdateTypes": ["major", "minor", "patch"],
  "groupName": "my-group-name",
  "commitMessagePrefix": "chore(component):",
  "labels": ["component", "type"],
  "prPriority": 25,
  "minimumReleaseAge": "7 days"
}
```

### Step 4: Test the Rule

```bash
# Validate configuration
npx renovate-config-validator renovate.json

# Test with dry-run
RENOVATE_DRY_RUN=full renovate --print-config
```

### Example: Adding a New Application

```json
{
  "description": "MyApp - New application with 5-day stabilization",
  "matchFileNames": ["apps/myapp/**/*.yaml", "argocd/applications/myapp.yaml"],
  "matchDatasources": ["helm", "docker"],
  "groupName": "myapp-updates",
  "commitMessagePrefix": "chore(myapp):",
  "labels": ["myapp", "application"],
  "prPriority": 10,
  "minimumReleaseAge": "5 days"
}
```

---

## Troubleshooting

### Issue: Dependency Not Detected

**Symptoms**: Renovate doesn't create PRs for a dependency

**Diagnosis**:

1. Check if the manager is enabled in `enabledManagers`
2. Verify file patterns match your files
3. Check if dependency is excluded by a package rule
4. Review Renovate logs for extraction errors

**Solutions**:

- Add missing manager to `enabledManagers`
- Adjust file patterns in package rules
- Remove or modify exclusion rules
- Add custom regex manager if needed

### Issue: Too Many PRs

**Symptoms**: Renovate creates many individual PRs

**Solutions**:

1. **Add grouping**:

   ```json
   {
     "matchFileNames": ["apps/**/*.yaml"],
     "groupName": "apps-updates"
   }
   ```

2. **Adjust schedule**:

   ```json
   {
     "schedule": ["before 6am on monday"]
   }
   ```

3. **Increase stabilization**:

   ```json
   {
     "minimumReleaseAge": "7 days"
   }
   ```

### Issue: Private Registry Authentication

**Symptoms**: Renovate can't access private OCI charts

**Solutions**:

1. Verify `hostRules` configuration:

   ```json
   {
     "matchHost": "registry.example.com",
     "hostType": "docker"
   }
   ```

2. Check CI/CD variables:
   - `RENOVATE_TOKEN` - GitLab API access
   - `DOCKER_HUB_USERNAME` / `DOCKER_HUB_TOKEN` - Registry credentials

3. Test authentication:

   ```bash
   echo "$PASSWORD" | helm registry login registry.example.com -u username --password-stdin
   ```

### Issue: Version Not Updating

**Symptoms**: Renovate detects update but doesn't create PR

**Diagnosis**:

1. Check `minimumReleaseAge` - version might be too new
2. Check `allowedVersions` - version might be blocked
3. Check `ignoreUnstable` - version might be pre-release

**Solutions**:

- Wait for stabilization period to pass
- Adjust `allowedVersions` constraint
- Set `ignoreUnstable: false` for specific package

---

## Best Practices

### 1. Stabilization Periods

Use longer stabilization for critical components:

- **Critical infrastructure** (ArgoCD, Longhorn): 14 days
- **Network components** (Traefik, Cert-Manager): 7 days
- **Applications**: 3-5 days
- **CI/CD tools**: 3-7 days
- **Security patches**: 0 days

### 2. Grouping Strategy

Group related updates to reduce PR noise:

- **By component**: `{{parentDir}}-helm-charts`
- **By update type**: `apps-patch-updates`
- **By criticality**: `infrastructure-updates`

### 3. Priority Assignment

Assign priorities based on impact:

- **Security**: 100 (immediate attention)
- **Critical infra**: 40-50 (high priority)
- **Applications**: 0-20 (normal priority)
- **Breaking changes**: -10 (review carefully)

### 4. Testing Workflow

1. **Review PR**: Check changelog and breaking changes
2. **Test locally**: `kustomize build` to verify manifests
3. **Merge PR**: Approve and merge to main branch
4. **Manual sync**: Sync application in ArgoCD UI
5. **Monitor**: Watch for errors in ArgoCD and application logs

### 5. Version Pinning

- **Helm charts**: Pin to specific versions (e.g., `1.2.3`)
- **Container images**: Pin to tags + digests (e.g., `v1.2.3@sha256:...`)
- **GitHub URLs**: Pin to version tags (e.g., `v1.2.3`), not branches

### 6. Custom Regex Patterns

When adding custom regex:

- **Test thoroughly**: Use regex101.com to validate
- **Be specific**: Avoid overly broad patterns
- **Document**: Add clear description
- **Handle edge cases**: Consider versions with/without 'v' prefix

---

## Common Scenarios

### Scenario 1: Adding a New Helm Chart

1. Add chart to `kustomization.yaml`:

   ```text
   helmCharts:
     - name: my-chart
       repo: https://charts.example.com
       version: 1.0.0
   ```

2. Renovate automatically detects it (no config change needed)

3. Optionally add custom rule for specific handling:

   ```json
   {
     "matchFileNames": ["apps/myapp/kustomization.yaml"],
     "matchPackageNames": ["my-chart"],
     "minimumReleaseAge": "5 days"
   }
   ```

### Scenario 2: Blocking a Major Version

Block Helm v4 until Kustomize supports it:

```json
{
  "matchDatasources": ["github-releases"],
  "matchPackageNames": ["helm/helm"],
  "allowedVersions": "<4.0.0"
}
```

### Scenario 3: Tracking Custom Tool Version

Add annotation to `.gitlab-ci.yml`:

```text
# renovate: datasource=github-releases depName=kubernetes/kubernetes
KUBERNETES_VERSION: "1.35.0"
```

Renovate automatically tracks it via custom regex manager.

---

## Resources

- **Renovate Documentation**: <https://docs.renovatebot.com/>
- **Configuration Options**:
  <https://docs.renovatebot.com/configuration-options/>
- **Regex Manager Guide**:
  <https://docs.renovatebot.com/modules/manager/regex/>
- **ArgoCD Integration**:
  <https://docs.renovatebot.com/modules/manager/argocd/>

---

## Maintenance

### Regular Tasks

**Weekly**:

- Review and merge Renovate PRs
- Check dependency dashboard for pending updates

**Monthly**:

- Review package rules for effectiveness
- Check for unused managers or rules
- Update stabilization periods if needed

**Quarterly**:

- Review entire configuration
- Update documentation
- Test dry-run mode for validation

### Configuration Updates

When updating `renovate.json`:

1. Validate syntax: `npx renovate-config-validator renovate.json`
2. Test with dry-run: `RENOVATE_DRY_RUN=full renovate`
3. Commit changes with descriptive message
4. Monitor first few PRs for issues

---

## Support

For issues or questions:

1. Check this guide first
2. Review Renovate logs in GitLab CI
3. Consult official Renovate documentation
4. Test changes with dry-run mode before applying

---

**Last Updated**: 2026-01-03
**Configuration Version**: 2.0 (after comprehensive review)
