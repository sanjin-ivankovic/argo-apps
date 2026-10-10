# ============================================================================
# ArgoCD GitOps Repository Makefile
# ============================================================================
#
# Local helpers for linting, validation, and cluster bootstrap. CI runs the
# authoritative checks (see .gitlab-ci.yml); these targets mirror them for
# local use.
#
# Usage:
#   make help              - Show this help
#   make lint-docs         - Lint all markdown files
#   make lint-yaml         - Lint all YAML files
#   make validate          - Run all lint checks
#   make validate-app APP=apps/<tier>/<name>  - Validate one app dir
#   make bootstrap         - Apply the app-of-apps bootstrap (argocd/)
#
# ============================================================================

.PHONY: help setup lint-docs lint-yaml validate validate-app kryptos-validate \
	bootstrap bootstrap-repo-secret bootstrap-root sync-all status kryptos clean
.DEFAULT_GOAL := help

# ============================================================================
# Configuration
# ============================================================================

MARKDOWNLINT_CONFIG := .config/.markdownlint-cli2.jsonc
YAMLLINT_CONFIG := .config/.yamllint
ARGOCD_NAMESPACE := argocd

# ============================================================================
# Help
# ============================================================================

help: ## Show this help message
	@echo "ArgoCD GitOps Repository - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# Setup
# ============================================================================

setup: ## Install pre-commit hooks and development dependencies
	@echo "Installing pre-commit hooks..."
	@pre-commit install
	@pre-commit install --hook-type commit-msg
	@echo "Done. Pre-commit hooks are now active."

# ============================================================================
# Linting
# ============================================================================

lint-docs: ## Lint all markdown files with markdownlint-cli2
	@echo "Linting markdown files..."
	@markdownlint-cli2 --config $(MARKDOWNLINT_CONFIG) "**/*.md" "#node_modules" "#.archive"

lint-yaml: ## Lint all YAML files
	@echo "Linting YAML files..."
	@yamllint -c $(YAMLLINT_CONFIG) .

validate: lint-docs lint-yaml ## Run all lint checks
	@echo "✅ All validation checks passed"

# ============================================================================
# App validation (mirrors CI validate:apps for a single app dir)
# ============================================================================

validate-app: ## Validate one app: make validate-app APP=apps/<tier>/<name>
	@if [ -z "$(APP)" ]; then \
		echo "❌ Error: APP not set"; \
		echo "Usage: make validate-app APP=apps/<tier>/<name>"; \
		exit 1; \
	fi
	@python3 .ci/scripts/validate_app.py $(APP)

kryptos-validate: ## Validate kryptos secret configs (kryptos/configs/)
	@kryptos validate

# ============================================================================
# ArgoCD Bootstrap (app-of-apps: argocd/root.yaml -> argocd/apps-set.yaml)
# ============================================================================

bootstrap: ## Apply the app-of-apps bootstrap (root Application + ApplicationSet)
	@echo "🚀 Bootstrapping the app-of-apps..."
	kubectl apply -k argocd/
	@echo ""
	@echo "✅ Root Application + ApplicationSet applied"
	@echo ""
	@echo "Next steps:"
	@echo "1. Get admin password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
	@echo "2. Port-forward: kubectl port-forward svc/argocd-server -n argocd 8080:443"
	@echo "3. Create Git repository secret (make bootstrap-repo-secret SSH_KEY_PATH=...)"
	@echo "4. Manually sync applications in the ArgoCD UI (auto-sync is disabled)"

bootstrap-repo-secret: ## Create Git repository secret (requires SSH_KEY_PATH env var)
	@if [ -z "$(SSH_KEY_PATH)" ]; then \
		echo "❌ Error: SSH_KEY_PATH environment variable not set"; \
		echo "Usage: make bootstrap-repo-secret SSH_KEY_PATH=~/.ssh/id_ed25519"; \
		exit 1; \
	fi
	@echo "Creating Git repository secret..."
	kubectl create secret generic gitlab-repo-secret \
		-n $(ARGOCD_NAMESPACE) \
		--from-literal=type=git \
		--from-literal=url=ssh://git@source.example.com/example-org/argo-apps.git \
		--from-file=sshPrivateKey=$(SSH_KEY_PATH) \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl label secret gitlab-repo-secret \
		-n $(ARGOCD_NAMESPACE) \
		argocd.argoproj.io/secret-type=repository --overwrite
	@echo "✅ Git repository secret created"

bootstrap-root: ## Apply only the root ArgoCD Application
	@echo "Applying root ArgoCD Application..."
	kubectl apply -f argocd/root.yaml
	@echo "✅ Root Application created"
	@echo ""
	@echo "Monitor deployment:"
	@echo "  kubectl get applications -n argocd -w"

# ============================================================================
# ArgoCD Operations
# ============================================================================

sync-all: ## Sync all ArgoCD applications
	@echo "Syncing all applications..."
	@argocd app sync -l argocd.argoproj.io/instance=apps
	@echo "✅ All applications synced"

status: ## Show status of all ArgoCD applications
	@kubectl get applications -n $(ARGOCD_NAMESPACE)

# ============================================================================
# Secret Management (kryptos is a released binary, run from the repo root —
# it reads kryptos.toml to find kryptos/configs/; see kryptos.toml for install)
# ============================================================================

kryptos: ## Run the kryptos secret management TUI
	@kryptos

# ============================================================================
# Cleanup
# ============================================================================

clean: ## Remove temporary files
	@echo "Cleaning temporary files..."
	@find . -name ".DS_Store" -delete
	@echo "✅ Cleanup complete"
