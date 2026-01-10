#!/usr/bin/env bash
# Bootstrap script for configuring Git repository in ArgoCD
# This script performs Stage 1b: Git repository configuration

set -euo pipefail

ARGOCD_NAMESPACE="argocd"
REPO_URL="git@github.com:m4dsurg3on/argo-apps.git"
SECRET_NAME="github-repo-secret"

echo "🔐 Stage 1b: Configuring Git repository in ArgoCD"
echo "=================================================="

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl is not installed or not in PATH"
    exit 1
fi

# Check if ArgoCD namespace exists
if ! kubectl get namespace "${ARGOCD_NAMESPACE}" &> /dev/null; then
    echo "❌ Error: ArgoCD namespace '${ARGOCD_NAMESPACE}' does not exist"
    echo "   Run bootstrap/install-argocd.sh first"
    exit 1
fi

# Check if ArgoCD server is running
if ! kubectl get pods -n "${ARGOCD_NAMESPACE}" -l app.kubernetes.io/name=argocd-server | grep -q Running; then
    echo "⚠️  Warning: ArgoCD server is not running"
    echo "   Waiting 30 seconds for ArgoCD to start..."
    sleep 30
fi

# Prompt for SSH private key path
echo ""
echo "📝 SSH Key Configuration"
echo "   Repository: ${REPO_URL}"
echo ""
read -r -p "Enter path to SSH private key for GitHub (default: ~/.ssh/id_rsa): " SSH_KEY_PATH
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_rsa}"

# Validate SSH key exists
if [[ ! -f "${SSH_KEY_PATH}" ]]; then
    echo "❌ Error: SSH key not found at ${SSH_KEY_PATH}"
    exit 1
fi

# Create repository secret
echo "🔑 Creating Git repository secret..."
kubectl create secret generic "${SECRET_NAME}" \
    -n "${ARGOCD_NAMESPACE}" \
    --from-literal=type=git \
    --from-literal=url="${REPO_URL}" \
    --from-file=sshPrivateKey="${SSH_KEY_PATH}" \
    --dry-run=client -o yaml | \
    kubectl label -f - \
        argocd.argoproj.io/secret-type=repository \
        --local -o yaml | \
    kubectl apply -f -

# Verify secret was created
if kubectl get secret "${SECRET_NAME}" -n "${ARGOCD_NAMESPACE}" &> /dev/null; then
    echo "✅ Git repository secret created successfully"
else
    echo "❌ Error: Failed to create repository secret"
    exit 1
fi

# Optionally add repository via ArgoCD CLI if available
if command -v argocd &> /dev/null; then
    echo ""
    echo "🔧 Adding repository via ArgoCD CLI..."

    # Get ArgoCD admin password
    ARGOCD_PASSWORD=$(kubectl -n "${ARGOCD_NAMESPACE}" get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)

    # Port-forward ArgoCD server (background)
    kubectl port-forward svc/argocd-server -n "${ARGOCD_NAMESPACE}" 8080:443 > /dev/null 2>&1 &
    PF_PID=$!
    sleep 2

    # Login to ArgoCD
    argocd login localhost:8080 --username admin --password "${ARGOCD_PASSWORD}" --insecure --grpc-web || {
        echo "⚠️  Warning: Failed to login to ArgoCD CLI"
        echo "   Repository secret created, but CLI configuration skipped"
        kill $PF_PID 2>/dev/null || true
        exit 0
    }

    # Add repository
    argocd repo add "${REPO_URL}" \
        --ssh-private-key-path "${SSH_KEY_PATH}" \
        --insecure || {
        echo "⚠️  Warning: Failed to add repository via CLI"
        echo "   Repository secret exists, you can add it manually in UI"
    }

    # Cleanup port-forward
    kill $PF_PID 2>/dev/null || true

    echo "✅ Repository added via ArgoCD CLI"
else
    echo ""
    echo "ℹ️  ArgoCD CLI not found. Repository secret created."
    echo "   You can add the repository manually in ArgoCD UI or install CLI:"
    echo "   brew install argocd"
fi

echo ""
echo "✅ Git repository configuration complete!"
echo ""
echo "📋 Next step:"
echo "   kubectl apply -f bootstrap/infrastructure.yaml"
echo ""
