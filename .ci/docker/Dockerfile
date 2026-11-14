# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#
# argo-apps-ci — CI image for the ArgoCD GitOps pipeline.
#
# THIN LAYER over the shared ci-base (homelab/ci-components): ci-base already
# carries the common toolchain (git, gitleaks, cosign, shellcheck, yamllint,
# markdownlint-cli2, pytest/pyyaml/tqdm/requests, yq, trivy, python3, nodejs,
# docker CLI) + the publish/sanitize tooling at /opt/ci. This image only adds
# the argo-specific tools: helm, kustomize, kubeconform and the CRDs-catalog.
#
# Non-obvious by design (don't "fix" without reading the README):
#   - runs as root, no USER/HEALTHCHECK — ephemeral CI pods, root-writable cache
#   - the ci-base ref is tag@sha256:<digest> so Renovate pins the digest (a
#     ci-base rebuild lands here as a digest-bump PR, never silently)

# No `# renovate:` annotation here on purpose: the native dockerfile manager
# already sees this ARG through `FROM docker:${DOCKER_VERSION}` and maintains
# tag+digest. An annotation extracts the same line a second time, and whichever
# write loses the race logs "Cannot find replaceString in current file content".
ARG DOCKER_VERSION=29.9.3-cli@sha256:4d742ab934c2149b628bf26369ac3ec51cb91e2e28fe6722a0e86a6d6efc4bd5

# fetcher: download + checksum-verify each binary, one RUN per tool so a
# single-tool Renovate bump only busts that tool's layer. curl/tar/xz live here
# only — never in the final image.
FROM docker:${DOCKER_VERSION} AS fetcher

# renovate: datasource=github-releases depName=helm/helm
ARG HELM_VERSION=4.3.2
# renovate: datasource=github-releases depName=kubernetes-sigs/kustomize
ARG KUSTOMIZE_VERSION=5.8.1
# renovate: datasource=github-releases depName=yannh/kubeconform
ARG KUBECONFORM_VERSION=0.8.0
# renovate: datasource=git-refs depName=datreeio/CRDs-catalog packageName=https://github.com/datreeio/CRDs-catalog.git currentValue=main
ARG CRDS_CATALOG_REF=5f127a5ac3655e83d40f7ad8d4b7392c89e36b38

RUN apk add --no-cache curl tar xz && mkdir -p /out/usr/local/bin /out/opt

# Helm — keep the real filename so the upstream .sha256sum (which names it) verifies.
RUN cd /tmp && \
  curl -fsSL -O "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" && \
  curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz.sha256sum" | sha256sum -c - && \
  tar xz -f "helm-v${HELM_VERSION}-linux-amd64.tar.gz" && \
  mv /tmp/linux-amd64/helm /out/usr/local/bin/ && \
  /out/usr/local/bin/helm version

RUN curl -fsSL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_linux_amd64.tar.gz" -o /tmp/kustomize.tgz && \
  curl -fsSL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/checksums.txt" \
    | grep "kustomize_v${KUSTOMIZE_VERSION}_linux_amd64.tar.gz" | awk '{print $1"  /tmp/kustomize.tgz"}' | sha256sum -c - && \
  tar xz -f /tmp/kustomize.tgz -C /out/usr/local/bin/ kustomize && \
  /out/usr/local/bin/kustomize version

RUN curl -fsSL "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-amd64.tar.gz" -o /tmp/kubeconform.tgz && \
  curl -fsSL "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/CHECKSUMS" \
    | grep 'kubeconform-linux-amd64.tar.gz' | awk '{print $1"  /tmp/kubeconform.tgz"}' | sha256sum -c - && \
  tar xz -f /tmp/kubeconform.tgz -C /out/usr/local/bin/ kubeconform && \
  /out/usr/local/bin/kubeconform -v

# CRDs-catalog (kubeconform -schema-location). Pinned to a commit, not main, so
# an upstream schema removal is an auditable PR; the commit SHA is the pin.
RUN curl -fsSL "https://github.com/datreeio/CRDs-catalog/archive/${CRDS_CATALOG_REF}.tar.gz" -o /tmp/crds-catalog.tgz && \
  mkdir -p /out/opt/crds-catalog && \
  tar -xzf /tmp/crds-catalog.tgz -C /out/opt/crds-catalog --strip-components=1 && \
  echo "crds-catalog: ${CRDS_CATALOG_REF} ($(find /out/opt/crds-catalog -name '*.json' | wc -l) schemas)"

# --- final image: ci-base + the argo-apps-specific layer ---
# renovate: datasource=docker depName=registry.example.com/homelab/ci-components/ci
FROM registry.example.com/homelab/ci-components/ci:latest@sha256:3d0ebcc8a1ef45d00f8a2d05d509bc4a628fad79634fca00568aa99adc116346

LABEL maintainer="maintainer@example.io"
LABEL org.opencontainers.image.title="argo-apps-ci"
LABEL org.opencontainers.image.description="CI image: ci-base + Helm, Kustomize, Kubeconform, CRDs-catalog"
LABEL org.opencontainers.image.source="https://source.example.com/example-org/argo-apps"
LABEL org.opencontainers.image.licenses="MIT"

# Kubernetes API version kubeconform validates against — single source for
# validate_app.py (reads the env var). Declared in the FINAL stage so the ENV
# can consume it. Not Renovate-tracked: kubeconform resolves schemas from
# yannh/kubernetes-json-schema, which publishes them as directories on master,
# so a kubernetes/kubernetes bump lands on a version with no schema tree.
ARG KUBERNETES_VERSION=1.36.3
ENV KUBECONFORM_KUBERNETES_VERSION=${KUBERNETES_VERSION}

COPY --from=fetcher /out/usr/local/bin/ /usr/local/bin/
COPY --from=fetcher /out/opt/crds-catalog/ /opt/crds-catalog/

# Smoke-test the argo-specific tools (ci-base smoke-tests the rest).
RUN echo "=== argo-apps CI layer ===" && \
  echo "helm: $(helm version --short)" && \
  echo "kustomize: $(kustomize version)" && \
  echo "kubeconform: $(kubeconform -v)" && \
  echo "crds-catalog: $(find /opt/crds-catalog -name '*.json' | wc -l) schemas" && \
  echo "=========================="

WORKDIR /workspace
CMD ["/bin/bash"]
