#!/bin/bash
set -e

echo "=========================================="
echo "Scanning for Plaintext Secrets"
echo "=========================================="

FINDINGS=0

# Common file patterns and exclusions (defined once, reused everywhere)
YAML_FILES=('*.yaml' '*.yml')
EXCLUDES=(':!_archive/*' ':!apps/*/secrets/*' ':!infrastructure/*/secrets/*')

# Helper function to run git grep once and display results
check_pattern() {
    local pattern="$1"
    local message="$2"
    local result

    if result=$(git grep -E "$pattern" -- "${YAML_FILES[@]}" "${EXCLUDES[@]}" 2>/dev/null); then
        echo "⚠️  $message"
        echo "$result"
        return 0
    fi
    return 1
}

echo "Searching for potential plaintext secrets..."
echo ""

# Base64-encoded secrets (40+ characters minimum for real secrets)
check_pattern '(password|apikey|api_key|token|secret):\s*['\''"]?[A-Za-z0-9+/]{40,}={0,2}['\''"]?\s*$' \
    "Found potential base64-encoded secret in plaintext" && ((FINDINGS++))

# AWS-style access keys (AKIA + 16 uppercase alphanumeric)
check_pattern '(aws_access_key|access_key_id):\s*['\''"]?AKIA[A-Z0-9]{16}['\''"]?' \
    "Found potential AWS access key in plaintext" && ((FINDINGS++))

# GitHub/GitLab personal access tokens
check_pattern '(github_token|gitlab_token|gh[ps]_[A-Za-z0-9_]{36,})' \
    "Found potential GitHub/GitLab token in plaintext" && ((FINDINGS++))

# Check for unsealed secret files
echo ""
echo "Checking secret files..."

while IFS= read -r -d '' file; do
    if ! grep -q "kind: SealedSecret" "$file"; then
        echo "⚠️  Secret file is not a SealedSecret: $file"
        ((FINDINGS++))
    fi
done < <(find apps infrastructure -type f -path '*/secrets/*' -name '*secret*.yaml' -print0 2>/dev/null)

# Report results
echo ""
if [ "$FINDINGS" -gt 0 ]; then
    echo "=========================================="
    echo "Security scan found $FINDINGS potential issues"
    echo "Please review and ensure secrets are properly sealed"
    echo "=========================================="
    exit 1
else
    echo "=========================================="
    echo "No plaintext secrets detected ✓"
    echo "=========================================="
fi
