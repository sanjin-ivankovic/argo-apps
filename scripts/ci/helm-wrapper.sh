#!/bin/bash
# Helm wrapper for Kustomize to inject registry credentials into isolated environment
#
# Problem: Kustomize uses --enable-helm which invokes Helm in an isolated environment.
# This environment has a custom HELM_CONFIG_HOME and strips most environment variables,
# breaking registry authentication for private OCI chart pulls.
#
# Solution: Copy the Docker config (created by 'docker login') to where Helm expects it
# within the isolated HELM_CONFIG_HOME directory.
#
# Additional: Handle Helm v4 compatibility with Kustomize by stripping legacy -c flag

# Determine source config file (set by generate-pipeline.py via WRAPPER_HELM_CONFIG)
if [ -n "$WRAPPER_HELM_CONFIG" ]; then
    SOURCE_CONFIG="$WRAPPER_HELM_CONFIG"
else
    # Fallback to standard Docker config location
    SOURCE_CONFIG="${DOCKER_CONFIG:-$HOME/.docker}/config.json"
fi

# Copy credentials to Helm's expected location within isolated config home
# Helm looks for registry credentials at $HELM_CONFIG_HOME/registry/config.json
if [ -n "$HELM_CONFIG_HOME" ] && [ -f "$SOURCE_CONFIG" ]; then
    HELM_REGISTRY_DIR="$HELM_CONFIG_HOME/registry"
    mkdir -p "$HELM_REGISTRY_DIR"
    cp "$SOURCE_CONFIG" "$HELM_REGISTRY_DIR/config.json"
fi

# Filter out legacy -c flag for Helm v4 compatibility
# Kustomize v5.x calls 'helm version -c --short' but Helm v4 removed the -c flag
FILTERED_ARGS=()
for arg in "$@"; do
    if [ "$arg" != "-c" ]; then
        FILTERED_ARGS+=("$arg")
    fi
done

# Execute actual Helm command with filtered arguments
exec /usr/local/bin/helm "${FILTERED_ARGS[@]}"
