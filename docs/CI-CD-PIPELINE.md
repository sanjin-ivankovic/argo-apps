# CI/CD Pipeline Documentation

This document describes the GitLab CI/CD pipeline for the ArgoCD GitOps
repository.

## Overview

The CI/CD pipeline provides automated validation, dependency management, and
security scanning for Kubernetes manifests and Helm charts. It ensures code
quality and security before changes are merged and deployed.

## Pipeline Stages

### 1. Lint Stage

**Job: `lint:yaml`**

- Validates YAML syntax across all manifest files
- Uses yamllint with project-specific configuration (`.yamllint`)
- Runs on merge requests and main branch when YAML files change
- Ensures consistent YAML formatting and catches syntax errors early

### 2. Renovate Stage

**Job: `renovate`**

- Automated dependency updates for Helm charts and Docker images
- Runs on scheduled pipelines (configure in GitLab: CI/CD > Schedules)
- Manual trigger available via web UI with dry-run mode
- Creates merge requests for dependency updates
- Configuration in `renovate.json`

**Features:**

- Helm chart version updates (both public and custom OCI registries)
- Docker image updates in Kubernetes manifests
- Grouped updates by application for atomic deployments
- Conservative update strategy with testing periods
- Separate handling for critical infrastructure components

### 3. Validate Stage (Dynamic Child Pipeline)

**Job: `generate:child-pipeline`**

- Analyzes changed files using Python script
- Generates a dynamic child pipeline YAML
- Creates separate validation jobs for each affected app/infrastructure
  component
- Outputs pipeline configuration as artifact

**Job: `trigger:validation`**

- Triggers the generated child pipeline
- Uses `strategy: depend` to wait for completion
- Each affected manifest gets its own parallel validation jobs:
  - **Kustomize Build**: Validates Kustomize can render the manifests
  - **Kubeconform Schema**: Validates against Kubernetes API schemas

**Benefits:**

- **Parallel Execution**: Each app validates independently and concurrently
- **Clear Visualization**: Separate job per component in pipeline UI
- **Scalable**: Automatically handles any number of apps
- **GitOps-Native**: Uses GitLab's child pipeline feature
- **No Complex Logic**: Change detection in Python, not bash

### 4. Security Stage

**Job: `security:scan-secrets`**

- Scans for potential plaintext secrets in manifests
- Ensures all secrets are SealedSecrets
- Checks for common secret patterns (passwords, API keys, tokens)
- Fails pipeline if plaintext secrets are detected

**Job: `security:check-privileges`**

- Identifies privileged containers and security concerns
- Checks for:
  - `privileged: true` containers
  - `hostNetwork: true` pods
  - `hostPID: true` pods
- Warns but doesn't fail pipeline (informational)

## Configuration

### Required GitLab CI/CD Variables

Configure these in GitLab: **Settings > CI/CD > Variables**

<!-- markdownlint-disable MD013 -->

| Variable           | Type   | Description                                         | Required |
| ------------------ | ------ | --------------------------------------------------- | -------- |
| `RENOVATE_TOKEN`   | Masked | GitLab Project Access Token or PAT with `api` scope | **Yes**  |
| `GITHUB_COM_TOKEN` | Masked | GitHub token for fetching release info              | Optional |

<!-- markdownlint-enable MD013 -->

#### Setting Up RENOVATE_TOKEN

**IMPORTANT**: Without this token, Renovate will run successfully but **will
not create any MRs or Issues**.

The GitLab CI default token (`CI_JOB_TOKEN`) only has read access. Renovate
needs a token with write permissions.

**Quick Setup:**

1. Go to: **Settings > Access Tokens** (Project Access Token) or **User
   Settings > Access Tokens** (Personal)
2. Create token with:
   - **Role**: Maintainer (for Project Access Token)
   - **Scopes**: `api` (includes repository read/write)
   - **Expiration**: 1 year or longer
3. Add to: **Settings > CI/CD > Variables**
   - **Key**: `RENOVATE_TOKEN`
   - **Value**: Your token
   - **Flags**: Masked ✅, Protected ✅

**Troubleshooting**: If Renovate runs but creates nothing, see
[RENOVATE-TROUBLESHOOTING.md](RENOVATE-TROUBLESHOOTING.md)

#### Creating RENOVATE_GITHUB_COM_TOKEN (Optional)

Many Helm charts and images reference GitHub releases. To avoid rate limiting:

1. Navigate to GitHub: **Settings > Developer settings > Personal access
   tokens**
2. Generate new token (classic) with `public_repo` scope
3. Copy token and add to CI/CD variables as `RENOVATE_GITHUB_COM_TOKEN`

### Setting Up Scheduled Pipelines

Renovate should run on a schedule to check for dependency updates regularly.

**Setup:**

1. Navigate to GitLab: **CI/CD > Schedules**
2. Click **New schedule**
3. Configure:
   - **Description**: "Renovate Dependency Updates"
   - **Interval Pattern**: Custom (`0 3 * * 1-5` for 3 AM weekdays)
   - **Target Branch**: `main`
   - **Activated**: ✓
4. Save schedule

The Renovate job will automatically run on scheduled pipelines.

### Pipeline Rules

The pipeline runs on:

- **Merge Requests**: Validates changed manifests only (optimized)
- **Main Branch**: Validates all manifests on changes
- **Scheduled**: Runs Renovate for dependency updates
- **Manual Trigger**: Available for testing Renovate in dry-run mode

## Usage

### Running Renovate Manually

For testing or immediate dependency updates:

1. Navigate to **CI/CD > Pipelines**
2. Click **Run pipeline**
3. Select branch: `main`
4. The Renovate job will appear as manual
5. Click play button to run (runs in dry-run mode for safety)

### Validating Local Changes

Before pushing, you can validate locally:

```bash
# Install required tools
brew install yamllint kustomize kubectl

# Validate YAML syntax
yamllint -c .yamllint .

# Test Kustomize build for an app
kubectl kustomize --enable-helm apps/postgresql/

# Test all apps
for dir in apps/*/; do
  echo "Building: $dir"
  kubectl kustomize --enable-helm "$dir"
done
```

### Understanding Renovate Updates

When Renovate creates a merge request:

1. **Review the changes carefully**:
   - Check changelog links in MR description
   - Verify version changes are intentional
   - Look for breaking changes or major updates

2. **CI/CD will validate**:
   - YAML syntax
   - Kustomize builds successfully
   - Kubernetes schema validation
   - No plaintext secrets

3. **After merging**:
   - Changes are automatically synced to main branch
   - **Important**: Manually sync applications in ArgoCD UI
   - ArgoCD auto-sync is intentionally disabled

## Renovate Configuration

### Update Strategy

Renovate is configured for **conservative, manual-approval updates**:

- **Minimum release age**: 3-30 days depending on criticality
- **No automerge**: All updates require manual review
- **Grouped by application**: Related updates bundled together
- **Scheduled runs**: Weekday mornings to avoid weekends

### Package Rules Priority

Updates are prioritized by risk and importance:

| Priority     | Component               | Release Age | Schedule |
| ------------ | ----------------------- | ----------- | -------- |
| Highest (30) | ArgoCD self-management  | 30 days     | Saturday |
| High (25)    | Longhorn storage        | 30 days     | Saturday |
| High (20)    | Traefik, Cert-Manager   | 21 days     | Saturday |
| Medium (15)  | PostgreSQL database     | 21 days     | Monday   |
| Medium (12)  | Valkey cache            | 14 days     | Monday   |
| Medium (10)  | Infrastructure          | 14 days     | Monday   |
| Medium (8)   | Monitoring stack        | 14 days     | Tuesday  |
| Standard (5) | Application Helm charts | 3 days      | Weekdays |
| Standard (0) | Docker images           | 3 days      | Weekdays |
| Low (-10)    | Major version updates   | 30 days     | Saturday |
| Urgent (100) | Security patches        | 0 days      | Anytime  |

### Custom OCI Registry

The pipeline handles custom Helm charts from `registry.example.com`:

- Extended testing period (7 days minimum)
- Grouped separately from public charts
- Requires registry authentication (configured in `hostRules`)

### Excluded Paths

Renovate ignores:

- `_archive/apps/` - Archived applications
- Test and example directories
- Git metadata and IDE files

## Troubleshooting

### Renovate Job Fails

**Common Issues:**

1. **Authentication failure**:
   - Verify `RENOVATE_TOKEN` is set and valid
   - Check token has required scopes
   - Token may have expired

2. **Rate limiting**:
   - Add `RENOVATE_GITHUB_COM_TOKEN` for GitHub releases
   - Check Renovate logs for rate limit messages

3. **Configuration error**:
   - Validate `renovate.json` syntax: `python3 -m json.tool renovate.json`
   - Check Renovate logs for parsing errors

### Validation Fails

**Kustomize build failures:**

```bash
# Test locally
cd apps/failing-app
kubectl kustomize --enable-helm .

# Common issues:
# - Invalid Helm chart version
# - Missing values.yaml
# - Incorrect resource references
```

**Kubeconform failures:**

```bash
# Test locally with kubeconform
kubectl kustomize --enable-helm apps/myapp | kubeconform \
  -kubernetes-version 1.31.0 \
  -schema-location default \
  -summary

# Common issues:
# - Deprecated API versions
# - Invalid resource fields
# - Missing required fields
```

### Security Scan Failures

**Plaintext secrets detected:**

- Never commit plaintext secrets
- Use Sealed Secrets: `scripts/seal-secrets.sh`
- Verify all `*secret*.yaml` files have `kind: SealedSecret`

**Privileged containers:**

- This is a warning, not a failure
- Review if privilege escalation is necessary
- Document justification in comments if required

### Pipeline Doesn't Trigger

**Check rules:**

- MR pipelines only run when relevant files change
- Main branch pipelines require changes to trigger
- Scheduled pipelines require schedule configuration
- Manual pipelines can always be triggered

## Best Practices

### Before Committing

1. **Validate locally**:

   ```bash
   yamllint -c .yamllint .
   kubectl kustomize --enable-helm apps/myapp/
   ```

2. **Check for secrets**:

   ```bash
   git grep -i "password:" -- '*.yaml'
   ```

3. **Test manifests**:

   ```bash
   kubectl apply -k apps/myapp --dry-run=server
   ```

### Reviewing Renovate MRs

1. **Check the dependency dashboard** (GitLab Issues)
2. **Review changelog links** in MR description
3. **Verify CI passes** all stages
4. **Test critical updates** in staging if available
5. **Merge and sync** in ArgoCD UI

### Handling Failed Pipelines

1. **Read the logs** - GitLab shows detailed error messages
2. **Fix locally first** - Test fixes before pushing
3. **Push incremental fixes** - Don't batch unrelated changes
4. **Ask for help** - Include logs when seeking assistance

## Integration with ArgoCD

### Post-Merge Workflow

After merging a Renovate MR or manual changes:

1. **Changes are in Git** (main branch)
2. **ArgoCD detects changes** but doesn't auto-sync
3. **Manual sync required**:
   - Navigate to <https://argo.example.com>
   - Find affected applications (Out of Sync status)
   - Click **Sync** > **Synchronize**
4. **Verify deployment** in ArgoCD UI

### Why Manual Sync?

Auto-sync is intentionally disabled to:

- Provide review opportunity before deployment
- Avoid automatic rollout of breaking changes
- Allow testing in development first
- Give control over deployment timing

## Maintenance

### Updating Tool Versions

Edit `.gitlab-ci.yml` variables:

```text
variables:
  KUBERNETES_VERSION: "1.31.0" # Update for new K8s versions
  KUSTOMIZE_VERSION: "v5.5.0" # Update for new Kustomize
  KUBECONFORM_VERSION: "v0.6.7" # Update for new kubeconform
```

### Updating Renovate

Edit `.gitlab-ci.yml` Renovate job:

```text
renovate:
  image: renovate/renovate:42.39 # Update version here
```

Or use `latest` (less stable):

```text
renovate:
  image: renovate/renovate:latest
```

### Adding Custom Validation

Add new jobs to `.gitlab-ci.yml`:

```text
validate:my-custom-check:
  stage: validate
  extends: .validation-job
  script:
    -  # Your validation logic
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
```

## Reference

- [Renovate Documentation](https://docs.renovatebot.com/)
- [GitLab CI/CD Pipelines](https://docs.gitlab.com/ee/ci/pipelines/)
- [Kustomize with Helm][kustomize-helm]
- [Kubeconform](https://github.com/yannh/kubeconform)
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)

[kustomize-helm]: https://kubectl.docs.kubernetes.io/references/kustomize/builtins/

## Support

For pipeline issues:

1. Check GitLab pipeline logs
2. Review this documentation
3. Consult ArgoCD UI for deployment status
4. Check Renovate dependency dashboard in GitLab Issues
