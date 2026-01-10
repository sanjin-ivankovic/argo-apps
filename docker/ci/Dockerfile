# syntax=docker/dockerfile:1@sha256:b6afd42430b15f2d2a4c5a02b919e98a525b785b1aaff16747d2f623364e39b6

# Base image version (can be overridden at build time)
ARG DOCKER_VERSION=29.1.3-cli@sha256:4fa0ee1f3a7e4354c4ea34558b6d4ee32859baf4973d4c8ccc8e7fe3dd730c04

FROM docker:${DOCKER_VERSION}

# Metadata
LABEL maintainer="maintainer@example.io"
LABEL org.opencontainers.image.title="argo-apps-ci"
LABEL org.opencontainers.image.description="CI tools for ArgoCD GitOps repository pipeline"
LABEL org.opencontainers.image.source="https://gitlab.example.com/homelab/argo-apps"
LABEL org.opencontainers.image.licenses="MIT"

# Binary tools
ARG HELM_VERSION
ARG KUSTOMIZE_VERSION
ARG KUBECONFORM_VERSION
ARG SHELLCHECK_VERSION
ARG GITLEAKS_VERSION

# Python packages
ARG PYYAML_VERSION
ARG TQDM_VERSION
ARG PYTEST_VERSION
ARG PYTEST_COV_VERSION
ARG REQUESTS_VERSION
ARG YAMLLINT_VERSION

# npm packages
ARG MARKDOWNLINT_VERSION

# Install base packages
RUN apk add --no-cache \
    bash \
    git \
    curl \
    jq \
    grep \
    nodejs \
    npm \
    python3 \
    py3-pip \
    ca-certificates \
    openssh-client

# Install Helm
RUN curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" | tar xz && \
    mv linux-amd64/helm /usr/local/bin/ && \
    rm -rf linux-amd64 && \
    helm version

# Install Kustomize
RUN curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | \
    bash -s -- ${KUSTOMIZE_VERSION} /usr/local/bin/ && \
    kustomize version

# Install kubeconform
RUN curl -sSL "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-amd64.tar.gz" | tar xz && \
    mv kubeconform /usr/local/bin/ && \
    kubeconform -v

# Install ShellCheck
RUN curl -fLs "https://github.com/koalaman/shellcheck/releases/download/${SHELLCHECK_VERSION}/shellcheck-${SHELLCHECK_VERSION}.linux.x86_64.tar.xz" | tar -xJ && \
    mv shellcheck-${SHELLCHECK_VERSION}/shellcheck /usr/local/bin/ && \
    rm -rf shellcheck-${SHELLCHECK_VERSION} && \
    shellcheck --version

# Install Gitleaks
RUN curl -fLs "https://github.com/gitleaks/gitleaks/releases/download/${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION#v}_linux_x64.tar.gz" | tar xz && \
    mv gitleaks /usr/local/bin/ && \
    gitleaks version

# Install markdownlint-cli2
RUN npm install -g markdownlint-cli2@${MARKDOWNLINT_VERSION} && \
    markdownlint-cli2 --version

# Install Python packages for CI scripts
RUN pip3 install --no-cache-dir --break-system-packages \
  "pyyaml==${PYYAML_VERSION}" \
  "tqdm==${TQDM_VERSION}" \
  "yamllint==${YAMLLINT_VERSION}" \
  "pytest==${PYTEST_VERSION}" \
  "pytest-cov==${PYTEST_COV_VERSION}" \
  "requests==${REQUESTS_VERSION}"

# Verify all tools are installed
RUN echo "=== Installed Tools ===" && \
    echo "helm: $(helm version --short)" && \
    echo "kustomize: $(kustomize version)" && \
    echo "kubeconform: $(kubeconform -v)" && \
    echo "yamllint: $(yamllint --version)" && \
    echo "shellcheck: $(shellcheck --version | grep version)" && \
    echo "markdownlint-cli2: $(markdownlint-cli2 --version)" && \
    echo "gitleaks: $(gitleaks version)" && \
    echo "python3: $(python3 --version)" && \
    echo "pytest: $(pytest --version)" && \
    echo "======================="

WORKDIR /workspace

CMD ["/bin/bash"]
