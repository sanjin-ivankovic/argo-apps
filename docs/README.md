# Documentation

Operator and portfolio documentation for `argo-apps`. The active platform
state is defined by `argocd/`, `apps/`, `.ci/`, `kryptos.toml`, and
`kryptos/configs/`; this directory explains it. Anything under `.archive/`
is historical, not current.

## Start Here

- **Portfolio overview:** [../README.md](../README.md)
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) — GitOps flow, the
  files generator, sync waves, bootstrap.
- **Applications:** [APPLICATIONS.md](APPLICATIONS.md) — the active app
  catalog and the per-app directory contract.
- **Infrastructure:** [INFRASTRUCTURE.md](INFRASTRUCTURE.md) — platform
  components, storage, and external-service proxying.
- **Operations:** [OPERATIONS.md](OPERATIONS.md) — day-2 runbook: sync,
  validate, inspect, rotate.
- **CI/CD:** [CI-CD-PIPELINE.md](CI-CD-PIPELINE.md) — native GitLab CI
  pipelines (one per repo) on a self-hosted runner.
- **Security:** [SECURITY.md](SECURITY.md) — secrets, SSO, and TLS.
- **Backup & DR:** [BACKUP-DR.md](BACKUP-DR.md) — what GitOps recreates vs.
  what needs data recovery.
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md) —
  symptom-based debugging.

## Also

- **Contributing:** [../CONTRIBUTING.md](../CONTRIBUTING.md)
- **ArgoCD bootstrap:** [../argocd/README.md](../argocd/README.md)
- **Kryptos secret configs:** [../kryptos/README.md](../kryptos/README.md)

## Source-of-Truth Rules

1. Manifests and CI scripts beat prose.
2. Apps live under `apps/<tier>/<app>/`; each needs a `config.yaml`.
3. ArgoCD discovers apps from `apps/*/*/config.yaml`.
4. The root Application syncs `argocd/`.
5. `.archive/` is historical only.
