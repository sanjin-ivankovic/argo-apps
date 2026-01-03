#!/usr/bin/env bash
# Bootstrap script for installing ArgoCD on a fresh k3s cluster
# This script performs Stage 1: Manual ArgoCD installation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ARGOCD_NAMESPACE="argocd"

echo "🚀 Stage 1: Installing ArgoCD manually on fresh k3s cluster"
echo "============================================================"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl is not installed or not in PATH"
    exit 1
fi

# Check if kustomize is available (needed for building manifests)
if ! command -v kustomize &> /dev/null; then
    echo "⚠️  Warning: kustomize not found. Installing via krew or downloading..."
    echo "   Please install kustomize: https://kustomize.io/"
    echo "   Or use: kubectl kustomize (if available)"
    exit 1
fi

# Create namespace if it doesn't exist
echo "📦 Creating namespace: ${ARGOCD_NAMESPACE}"
kubectl create namespace "${ARGOCD_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Install ArgoCD using kustomize from infrastructure/argocd
echo "📥 Installing ArgoCD from infrastructure/argocd/"
cd "${REPO_ROOT}/infrastructure/argocd"

# Build and apply ArgoCD manifests
echo "🔨 Building ArgoCD manifests..."

# Check if Traefik IngressRoute CRD exists
if kubectl get crd ingressroutes.traefik.io &> /dev/null; then
    echo "✅ Traefik CRDs found - including ingress resources"
else
    echo "⚠️  Traefik CRDs not found - IngressRoute will fail (expected)"
    echo "   IngressRoute will be deployed after Traefik is installed via GitOps"
fi

# Build and apply manifests
# If Traefik CRD doesn't exist, exclude ingress from kustomization build
if ! kubectl get crd ingressroutes.traefik.io &> /dev/null; then
    # Temporarily comment out ingress in kustomization.yaml (macOS/BSD compatible)
    sed -i '' 's/^  - ingress$/  # - ingress/' kustomization.yaml 2>/dev/null || \
    sed -i.bak 's/^  - ingress$/  # - ingress/' kustomization.yaml
    kustomize build . --load-restrictor LoadRestrictionsNone | \
        kubectl apply -n "${ARGOCD_NAMESPACE}" -f -
    # Restore original kustomization.yaml
    if [[ -f kustomization.yaml.bak ]]; then
        mv kustomization.yaml.bak kustomization.yaml
    else
        # Restore on macOS (sed -i '' creates backup differently)
        sed -i '' 's/^  # - ingress$/  - ingress/' kustomization.yaml
    fi
else
    # Traefik CRD exists - apply everything including ingress
    kustomize build . --load-restrictor LoadRestrictionsNone | \
        kubectl apply -n "${ARGOCD_NAMESPACE}" -f -
fi

# Wait for ArgoCD server to be ready
echo "⏳ Waiting for ArgoCD server to be ready..."
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=argocd-server \
    -n "${ARGOCD_NAMESPACE}" \
    --timeout=300s || {
    echo "⚠️  Warning: ArgoCD server not ready within timeout"
    echo "   Check status with: kubectl get pods -n ${ARGOCD_NAMESPACE}"
}

# Get initial admin password
echo ""
echo "✅ ArgoCD installation complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Get initial admin password:"
echo "      kubectl -n ${ARGOCD_NAMESPACE} get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
echo ""
echo "   2. Port-forward to access UI (Traefik not available yet):"
echo "      kubectl port-forward svc/argocd-server -n ${ARGOCD_NAMESPACE} 8080:443"
echo "      Then access: https://localhost:8080 (accept self-signed cert)"
echo ""
echo "   3. Configure Git repository:"
echo "      ./bootstrap/configure-repo.sh"
echo ""
echo "   4. Apply root application:"
echo "      kubectl apply -f bootstrap/root.yaml"
echo ""
