# CI Docker Image

Custom Docker image with pre-installed CI/CD tools for the ArgoCD GitOps
pipeline.

## Purpose

This image contains all tools needed for validating Kubernetes manifests and
Helm charts:

- **Docker CLI**: Container operations and image builds
- **kubectl**: Kubernetes cluster operations
- **Helm**: Package manager for Kubernetes
- **Kustomize**: Kubernetes manifest customization
- **kubeconform**: Kubernetes schema validation
- **Python 3**: Pipeline generation scripts with PyYAML

## Benefits

- **Faster pipelines**: No installation time per job (~30-60 seconds saved
  per job)
- **Consistent versions**: Tools locked to specific versions tracked by Renovate
- **Reduced bandwidth**: Download once, use many times
- **Simpler pipeline**: No complex `before_script` blocks

## Building the Image

The image is automatically built by GitLab CI when `docker/ci/**` files change.

### Manual Build

```bash
docker build \
  --build-arg DOCKER_VERSION=29.1.3-cli \
  --build-arg KUBERNETES_VERSION=1.34.2 \
  --build-arg KUSTOMIZE_VERSION=5.8.0 \
  --build-arg KUBECONFORM_VERSION=0.7.0 \
  --build-arg HELM_VERSION=3.19.2 \
  --tag ${CI_REGISTRY_IMAGE}/ci:latest \
  docker/ci/
```

### Push to Registry

```bash
docker push ${CI_REGISTRY_IMAGE}/ci:latest
```

> **Note**: The image is pushed to the GitLab Container Registry at
> `${CI_REGISTRY_IMAGE}/ci:latest` where `CI_REGISTRY_IMAGE` is your project's
> registry path (e.g., `registry.gitlab.com/username/argo-apps`)

## Usage in Pipeline

The image is referenced via the `$CI_IMAGE` variable in `.gitlab-ci.yml`:

```text
variables:
  CI_IMAGE: "${CI_REGISTRY_IMAGE}/ci:latest"

.base-job:
  image: $CI_IMAGE
```

All validation jobs automatically use this image with no installation overhead.

## Updating Tool Versions

To update tool versions:

1. Modify build args in `Dockerfile` (defaults) **OR**
2. Update variables in `.gitlab-ci.yml`:

   ```text
   variables:
     KUBERNETES_VERSION: "1.35.0"
     KUSTOMIZE_VERSION: "v5.9.0"
     KUBECONFORM_VERSION: "v0.8.0"
   ```

3. The `build:ci-image` job will automatically rebuild with new versions

## Installed Tools

<!-- markdownlint-disable MD013 -->

| Tool                | Purpose                | Version Source        | Default |
| ------------------- | ---------------------- | --------------------- | ------- |
| Docker CLI          | Container operations   | `DOCKER_VERSION`      | 29.1.3  |
| kubectl             | Kubernetes CLI         | `KUBERNETES_VERSION`  | 1.34.2  |
| Helm                | Helm package manager   | `HELM_VERSION`        | 3.19.2  |
| Kustomize           | Manifest customization | `KUSTOMIZE_VERSION`   | 5.8.0   |
| kubeconform         | Schema validation      | `KUBECONFORM_VERSION` | 0.7.0   |
| Python 3            | Pipeline scripts       | Alpine default        | 3.12.x  |
| PyYAML              | YAML processing        | Latest from pip       | -       |
| bash, git, curl, jq | Utility tools          | Alpine packages       | -       |

<!-- markdownlint-enable MD013 -->

> **Version Management**: All tool versions are tracked by Renovate and
> automatically updated via pull requests.

## Verification

After the image is built, it prints verification output:

```text
=== Installed Tools ===
kubectl: v1.34.2
helm: v3.19.2
kustomize: v5.8.0
kubeconform: v0.7.0
python3: 3.12.x
=======================
```
