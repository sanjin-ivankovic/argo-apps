# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32
#
# argo-apps-ci — CI image for the ArgoCD GitOps pipeline.
#
# THIN LAYER over the shared ci-base (homelab/ci-components): ci-base already
# carries the common toolchain (git, gitleaks, cosign, shellcheck, yamllint,
# markdownlint-cli2, pytest/pyyaml/tqdm/requests, yq, trivy, python3, nodejs,
# docker CLI) + the publish/sanitize tooling at /opt/ci. This image only adds
# the argo-specific tools: helm, kustomize, kubeconform, the CRDs-catalog, and
# the kryptos CLI (fetched via a BuildKit secret from the private example-org/kryptos
# package registry).
#
# Non-obvious by design (don't "fix" without reading the README):
#   - runs as root, no USER/HEALTHCHECK — ephemeral CI pods, root-writable cache
#   - the kryptos CLI is fetched with a BuildKit --secret (never a build-arg, so
#     it never lands in a layer); the ci-image component's setup_script +
#     build_args wire the token file + the --secret flag.
#   - the ci-base ref is tag@sha256:<digest> so Renovate pins the digest (a
#     ci-base rebuild lands here as a digest-bump PR, never silently)

# No `# renovate:` annotation here on purpose: the native dockerfile manager
# already sees this ARG through `FROM docker:${DOCKER_VERSION}` and maintains
# tag+digest. An annotation extracts the same line a second time, and whichever
# write loses the race logs "Cannot find replaceString in current file content".
ARG DOCKER_VERSION=29.7.2-cli@sha256:3f4743208d2338c934d7b8bcfbe1bb54c0b2355c510ad5e0f31c0c4a54bd704e

# fetcher: download + checksum-verify each binary, one RUN per tool so a
# single-tool Renovate bump only busts that tool's layer. curl/tar/xz live here
# only — never in the final image.
FROM docker:${DOCKER_VERSION} AS fetcher

# renovate: datasource=github-releases depName=helm/helm
ARG HELM_VERSION=4.2.4
# renovate: datasource=github-releases depName=kubernetes-sigs/kustomize
ARG KUSTOMIZE_VERSION=5.8.1
# renovate: datasource=github-releases depName=yannh/kubeconform
ARG KUBECONFORM_VERSION=0.8.0
# renovate: datasource=git-refs depName=datreeio/CRDs-catalog packageName=https://github.com/datreeio/CRDs-catalog.git currentValue=main
ARG CRDS_CATALOG_REF=5f127a5ac3655e83d40f7ad8d4b7392c89e36b38
# kryptos CLI — baked so validate:kryptos-configs can run `kryptos validate`.
# Downloaded from the example-org/kryptos GitLab Generic Package Registry (private,
# so the fetch needs a read token, mounted as a BuildKit secret — see below).
# renovate: datasource=gitlab-releases depName=example-org/kryptos registryUrl=https://source.example.com
ARG KRYPTOS_VERSION=v0.2.1

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

# kryptos CLI from the example-org/kryptos Generic Package Registry. The token is a
# BuildKit secret (id=kryptos_token) — NOT a build-arg, so it never lands in a
# layer. The generic-package path is /packages/generic/kryptos/<ver>/<file>
# (the goreleaser use_package_registry target); checksum-verified like the rest.
RUN --mount=type=secret,id=kryptos_token \
  KVER="${KRYPTOS_VERSION#v}" && \
  BASE="https://source.example.com/api/v4/projects/homelab%2Fkryptos/packages/generic/kryptos/${KVER}" && \
  TOKEN="$(cat /run/secrets/kryptos_token)" && \
  curl -fsSL -H "PRIVATE-TOKEN: ${TOKEN}" "${BASE}/kryptos_${KVER}_linux_amd64.tar.gz" -o /tmp/kryptos.tgz && \
  curl -fsSL -H "PRIVATE-TOKEN: ${TOKEN}" "${BASE}/checksums.txt" \
    | grep "kryptos_${KVER}_linux_amd64.tar.gz$" | awk '{print $1"  /tmp/kryptos.tgz"}' | sha256sum -c - && \
  tar xz -f /tmp/kryptos.tgz -C /out/usr/local/bin/ kryptos && \
  /out/usr/local/bin/kryptos validate --help >/dev/null && echo "kryptos ${KRYPTOS_VERSION} OK"

# --- final image: ci-base + the argo-apps-specific layer ---
# renovate: datasource=docker depName=registry.example.com/homelab/ci-components/ci
FROM registry.example.com/homelab/ci-components/ci:latest@sha256:73df8ef6835dbb69293cf60c53f0373abf407fc1830bfe4dfb60b1a3fc456ebb

LABEL maintainer="maintainer@example.io"
LABEL org.opencontainers.image.title="argo-apps-ci"
LABEL org.opencontainers.image.description="CI image: ci-base + Helm, Kustomize, Kubeconform, CRDs-catalog, kryptos"
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
  echo "kryptos: $(kryptos validate --help >/dev/null 2>&1 && echo present)" && \
  echo "=========================="

WORKDIR /workspace
CMD ["/bin/bash"]
