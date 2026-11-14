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

.PHONY: help setup lint-docs lint-yaml validate validate-app \
	bootstrap bootstrap-repo-secret bootstrap-root sync-all status clean
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

# Pulls the chart version pinned in $(APP)/kustomization.yaml into
# $(APP)/charts/<name>-<version>/. It never deletes: after a bump,
# validate-app names the old <name>-<old> dir, which you `git rm -r`.
vendor-chart: ## Vendor the pinned chart of a vendored app: make vendor-chart APP=apps/data/postgresql
	@test -n "$(APP)" || { echo "Usage: make vendor-chart APP=apps/data/<name>"; exit 1; }
	@python3 -c 'import sys,yaml; c=yaml.safe_load(open(sys.argv[1]))["helmCharts"][0]; print(c["repo"], c["name"], c["version"])' $(APP)/kustomization.yaml \
	  | { read -r repo name version; \
	      test ! -e "$(APP)/charts/$$name-$$version" || { echo "$(APP)/charts/$$name-$$version already exists"; exit 1; }; \
	      helm pull "$$repo/$$name" --version "$$version" --untar --untardir "$(APP)/charts/$$name-$$version" \
	        && echo "vendored $$name $$version into $(APP)/charts/$$name-$$version/"; }

# ============================================================================
# ArgoCD Bootstrap (app-of-apps: argocd/root.yaml -> argocd/apps-set.yaml)
# ============================================================================

bootstrap: ## Apply the ApplicationSet (argocd/); make bootstrap-root adds the root Application
	@echo "🚀 Bootstrapping the app-of-apps..."
	kubectl apply -k argocd/
	@echo ""
	@echo "✅ ApplicationSet applied (run make bootstrap-root for the root Application)"
	@echo ""
	@echo "Next steps:"
	@echo "1. Get admin password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
	@echo "2. Port-forward: kubectl port-forward svc/argocd-server -n argocd 8080:443"
	@echo "3. Create Git repository secret (make bootstrap-repo-secret SSH_KEY_PATH=...)"
	@echo "4. User-tier apps auto-sync; sync infra, data and services by hand in the ArgoCD UI"

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
# Cleanup
# ============================================================================

clean: ## Remove temporary files
	@echo "Cleaning temporary files..."
	@find . -name ".DS_Store" -delete
	@echo "✅ Cleanup complete"
