#!/bin/bash
# Helper script to create DHI.io registry SealedSecret

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DHI.io Docker Registry Secret Generator"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Get credentials
read -r -p "Enter your dhi.io username: " DHI_USERNAME
read -r -sp "Enter your dhi.io password: " DHI_PASSWORD
echo
echo

# Validate inputs
if [[ -z "$DHI_USERNAME" ]] || [[ -z "$DHI_PASSWORD" ]]; then
    echo "❌ Error: Username and password are required"
    exit 1
fi

echo "Creating SealedSecret..."

# Create the docker-registry secret and seal it
if kubectl create secret docker-registry dhi-registry-secret \
  --docker-server=dhi.io \
  --docker-username="$DHI_USERNAME" \
  --docker-password="$DHI_PASSWORD" \
  --namespace=traefik \
  --dry-run=client -o yaml | \
kubeseal --format=yaml \
  --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system \
  > "$(dirname "$0")/dhi-registry-sealed-secret.yaml"; then
    echo
    echo "✅ SealedSecret created successfully!"
    echo "📁 File: infrastructure/traefik/secrets/dhi-registry-sealed-secret.yaml"
    echo
    echo "Next steps:"
    echo "1. Review the generated file"
    echo "2. git add infrastructure/traefik/"
    echo "3. git commit -m 'feat(traefik): add DHI.io registry credentials'"
    echo "4. git push"
    echo "5. Manually sync Traefik in ArgoCD UI"
else
    echo "❌ Failed to create SealedSecret"
    exit 1
fi
