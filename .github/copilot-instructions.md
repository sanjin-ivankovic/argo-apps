# Copilot Instructions for argo-apps

## Big Picture Architecture

- **App-of-Apps Pattern**: ArgoCD manages itself and all infrastructure/apps via a central ApplicationSet (`argocd/applications/apps-set.yaml`).
- **Auto-Discovery**: All subdirectories in `apps/` are automatically deployed as ArgoCD applications using the Git directory generator.
  No manual ApplicationSet edits required.
- **Manual Sync Required**: Auto-sync is disabled for all apps. After pushing changes, you must manually sync in the ArgoCD UI
  (`https://argo.example.com`).
- **Helm & Kustomize**: Most apps use custom Helm charts (OCI registry: `oci://registry.example.com/homelab/helm-charts`),
  some use public charts (PostgreSQL, Valkey, Rancher), and a few use manifest-based Kustomize only.
- **Infrastructure**: Core components (ArgoCD, Traefik, Cert-Manager, MetalLB, Longhorn, Monitoring (commented out),
  Cloudflared, External Services, Sealed Secrets, Rancher) live in `infrastructure/` and are managed as separate ArgoCD apps.

## Developer Workflows

- **Bootstrap**: Deploy the stack with `kubectl apply -f bootstrap/root.yaml` or `kubectl apply -f argocd/kustomization.yaml`.
- **Secrets**: Always use `scripts/kryptos/` to generate SealedSecrets. Never commit plain secrets.
- **Testing**: Validate manifests locally with `kubectl apply -k apps/<app> --dry-run=server` before committing.
- **Syncing**: After pushing, manually sync apps in the ArgoCD UI. Use CLI (`argocd app sync <app>`) for automation.
- **CI/CD**: `.gitea/workflows/README.md` describes pipelines for validating manifests before cluster deployment.

## Project-Specific Conventions

- **Namespace = Directory Name**: Each app's namespace matches its directory name in `apps/` (except Rancher, which uses `cattle-system`).
- **Directory Structure**:
  - `apps/<app>/kustomization.yaml` (Helm or manifest)
  - `apps/<app>/values.yaml` (Helm values)
  - `apps/<app>/ingress/` (Traefik IngressRoute)
  - `apps/<app>/secrets/` (SealedSecrets)
- **Ingress**: Use Traefik IngressRoute CRDs, not standard Ingress.
  Domain pattern: `<app>.example.com`.
- **Secrets**: Per-app secret configs in `scripts/kryptos/configs/<app>.yaml`. All secrets must be SealedSecrets.
- **Database**: Shared PostgreSQL cluster (`apps/postgresql/`) serves affine and freshrss.
  Per-app DB jobs and SealedSecrets in `apps/postgresql/jobs/` and `apps/postgresql/secrets/`.
- **External Services**: Proxied via Traefik using Endpoints + Service + IngressRoute (`infrastructure/external-services/`).

## Integration Points & Patterns

- **Custom Helm Charts**: Most apps use charts from `oci://registry.example.com/homelab/helm-charts` (see CLAUDE.md for mapping).
  Current custom chart apps: affine, freshrss, home-assistant, it-tools, myspeed, omni-tools, privatebin, searxng, stirling-pdf, cloudflared.
- **Public Helm Charts**: PostgreSQL, Valkey, Rancher, Traefik, Longhorn, Monitoring, Cert-Manager, Sealed Secrets
  use official/public charts.
- **Monitoring**: Prometheus & Grafana stack in `infrastructure/monitoring/`.
- **Storage**: Longhorn for distributed block storage, PVCs provisioned for apps.
- **TLS**: Cert-manager issues wildcard certs for `*.example.com` using Cloudflare DNS01.

## Key Files & Directories

- `README.md`: Architecture, workflows, and conventions
- `CLAUDE.md`: AI agent guidance and architecture summary
- `bootstrap/root.yaml`: Initial bootstrap manifest
- `argocd/applications/apps-set.yaml`: ApplicationSet for auto-discovery
- `scripts/kryptos/`: SealedSecrets generator (Go-based CLI)
- `infrastructure/`: Core platform components
- `apps/`: All applications (auto-discovered)
- `.gitea/workflows/README.md`: CI/CD pipeline details

## Examples

- Add a new app: Create `apps/<app>/` with `kustomization.yaml`, `values.yaml` (if Helm-based), `ingress/`,
  and `secrets/` (if needed). Commit and push. ApplicationSet auto-discovers it. Sync in ArgoCD UI.
- Update a secret: Run `cd scripts/kryptos && ./kryptos`, select app, commit the new SealedSecret, and sync the app.
- Debug sync issues: Use `kubectl apply -k apps/<app> --dry-run=server` and check ArgoCD UI logs.
- Current applications: affine, freshrss, home-assistant, it-tools, myspeed, omni-tools, postgresql, privatebin, searxng, stirling-pdf, valkey

---

For more details, see `README.md`, `CLAUDE.md`, and per-app/infrastructure READMEs.
