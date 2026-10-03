# CI Docker Image

Custom Docker image with pre-installed CI/CD tools, used as the job image by
this repo's GitLab CI pipeline ([`.gitlab-ci.yml`](../../.gitlab-ci.yml)).
Published per repo as `registry.example.com/homelab/<repo>/ci:latest`.

## Purpose

This image contains every tool the lint / validate / image jobs need:

- **Docker CLI** — base image, container operations
- **Helm** — render charts for validation (pinned for Helm 4 + Kustomize)
- **Kustomize** — build manifests for validation
- **kubeconform** — Kubernetes schema validation (uses the baked
  datreeio CRDs-catalog at `/opt/crds-catalog`)
- **cosign** — OCI artifact signing (signs the CI image itself + per-app
  artifacts)
- **trivy** — vulnerability / config / IaC scanning (copied from the
  official image, base digest-pinned)
- **shellcheck**, **gitleaks**, **yamllint**, **markdownlint-cli2** —
  linting; the native CI jobs (`scan:secrets`, `lint:*`) call these binaries
  directly
- **Python 3** + pyyaml/tqdm/requests/pytest/pytest-cov — the
  `.ci/scripts/` validate + publish tooling (baked into `/opt/ci/`)

pre-commit is **not** installed: CI runs the linters/scanners as native
`.gitlab-ci.yml` jobs, and pre-commit is a local-only developer hook.

## Benefits

- **Faster pipelines** — no per-job tool install
- **Consistent, pinned versions** — see "Version model" below
- **Supply-chain hardened** — base images are digest-pinned; every fetched
  binary is checksum-verified at build (see "Supply chain")
- **Signed** — the image itself is cosign-signed on publish (`sign:ci-image`)

## Version model

Every tool version is a **Renovate-annotated `ARG` default in the Dockerfile** —
that is the single source of truth, so `docker build` needs no `--build-arg`:

```text
# renovate: datasource=github-releases depName=helm/helm
ARG HELM_VERSION=4.2.0
```

The base images carry a full `tag@sha256:<digest>` so the build base is
immutable; Renovate bumps the tag and digest together (`pinDigests`):

```text
# renovate: datasource=docker depName=docker versioning=docker
ARG DOCKER_VERSION=29.5.2-cli@sha256:9ba8e32...
```

All four repos (`argo-apps`, `helm-charts`, `kryptos`, `proxmox-infra`) use
this in-Dockerfile ARG-default model. (Under the former Argo pipeline the
versions were supplied via the kaniko `--build-arg` list in the WorkflowTemplate
— moving them into the Dockerfile is what lets the GitLab CI `build:ci-image`
job run plain `docker build`.)

## Supply chain

- **Base images** are pinned `tag@sha256:<digest>` (immutable).
- **Fetched binaries** (helm, kustomize, kubeconform, gitleaks, cosign)
  are verified against their upstream checksum file with `sha256sum -c`
  before install. A wrong version fails the build.
- **shellcheck** is the one exception — upstream publishes no checksum
  file for its release tarballs, so it is pinned by version only.

Renovate cannot recompute an arbitrary binary's checksum on a version
bump (no `getDigest` for github-releases/pypi/npm), which is why
verification is against the upstream checksum file at build time rather
than a pinned `*_CHECKSUM` build-arg.

## Runtime user

Runs as root by design — these are ephemeral one-shot CI job containers and
the root-writable caches expect it. No `USER`/`HEALTHCHECK`.

## Building

The image is built by the `build:ci-image` job in
[`.gitlab-ci.yml`](../../.gitlab-ci.yml) on a `main` push that touches
`.ci/docker/**` (or the baked `.ci/scripts/*.py`). That job runs `docker build`
against the runner's host Docker daemon and pushes to Harbor; the separate
`sign:ci-image` job cosign-signs the pushed manifest by digest. The build
context is the **repo root** so the Dockerfile can `COPY` `.ci/scripts/`.

### Manual build (locally)

No `--build-arg` needed — the ARG defaults are in the Dockerfile (context =
repo root):

```bash
docker build -f .ci/docker/Dockerfile \
  -t registry.example.com/example-org/argo-apps/ci:latest \
  .
```

## Verification

On build the image prints a verification block listing every installed
tool with its version (`=== Installed Tools ===`), so a broken install
fails at build time rather than on the first CI run.
