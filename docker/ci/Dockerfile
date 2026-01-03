# syntax=docker/dockerfile:1@sha256:b6afd42430b15f2d2a4c5a02b919e98a525b785b1aaff16747d2f623364e39b6

# Base image version (can be overridden at build time)
ARG DOCKER_VERSION=29.1.3-cli@sha256:4fa0ee1f3a7e4354c4ea34558b6d4ee32859baf4973d4c8ccc8e7fe3dd730c04

FROM docker:${DOCKER_VERSION}

# Metadata
LABEL maintainer="maintainer@example.com"
LABEL description="CI tools for ArgoCD GitOps repository validation"
LABEL org.opencontainers.image.source="https://gitlab.example.com/homelab/argo-apps"

# Tool versions (can be overridden at build time)
# renovate: datasource=github-releases depName=kubernetes/kubernetes
ARG KUBERNETES_VERSION=1.35.0
# renovate: datasource=github-releases depName=kubernetes-sigs/kustomize extractVersion=^kustomize/(?<version>.*)$
ARG KUSTOMIZE_VERSION=5.8.0
# renovate: datasource=github-releases depName=yannh/kubeconform
ARG KUBECONFORM_VERSION=0.7.0
# renovate: datasource=github-releases depName=helm/helm
ARG HELM_VERSION=3.19.4

# Install base packages
RUN apk add --no-cache \
    bash \
    git \
    curl \
    jq \
    grep \
    python3 \
    py3-pip \
    ca-certificates \
    openssh-client

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/v${KUBERNETES_VERSION}/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/ && \
    kubectl version --client

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

# Install Python packages for pipeline generation and sanitization
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Verify all tools are installed
RUN echo "=== Installed Tools ===" && \
    echo "kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client)" && \
    echo "helm: $(helm version --short)" && \
    echo "kustomize: $(kustomize version --short)" && \
    echo "kubeconform: $(kubeconform -v)" && \
    echo "python3: $(python3 --version)" && \
    echo "======================="

WORKDIR /workspace

CMD ["/bin/bash"]
