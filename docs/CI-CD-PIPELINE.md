# CI/CD Pipeline

CI runs on **GitLab CI** (`source.example.com`), one `.gitlab-ci.yml` per repo,
executed by a self-hosted GitLab Runner on a dedicated LXC. Each of the four
homelab repos (`argo-apps`, `helm-charts`, `kryptos`, `proxmox-infra`) defines
its own native pipeline. **Lint + validate run on every merge request** (so
Renovate/feature MRs get a ✓/✗ commit status), while the side-effecting jobs —
**publish, build, sign, release — only run on `main`** (or a `v*` tag for
kryptos releases). CD stays on ArgoCD with its manual-sync policy.

Running CI off-cluster keeps the cluster's RAM and Longhorn storage for
workloads rather than per-run pipeline pods.

## Architecture

```text
GitLab (source.example.com)
      │  push (main) / merge request / v* tag
      ▼
GitLab CI pipeline (.gitlab-ci.yml in each repo)
      │  jobs run on the homelab GitLab Runner
      ▼
gitlab-runner LXC (Docker executor, host docker socket)
      │  builds + pushes signed artifacts
      ▼
Harbor (registry.example.com) + cosign signatures
      │
      ▼
Native GitLab commit status (✓ / ✗ on the pipeline)
```

The runner is a dedicated LXC (`gitlab-runner`, in proxmox-infra) using the
**Docker executor bound to the host's Docker socket** — image builds run with
plain `docker build` against that daemon (no kaniko, no privileged DinD). Every
job carries `tags: [docker]` to target this runner. Job images come from
`registry.example.com/homelab/<repo>/ci:latest` (per-repo CI image, built and
cosign-signed by that repo's own `build:ci-image` + `sign:ci-image` jobs).

Each per-repo CI image is a **thin `FROM` layer** over the shared `ci-base`
image (`registry.example.com/homelab/ci-components/ci`, digest-pinned). `ci-base`
bakes the common toolchain — git, gitleaks, cosign, shellcheck, yamllint,
markdownlint-cli2, pytest, python3, nodejs, the Docker CLI, trivy, and yq — plus
the publish/sanitize Python tooling at `/opt/ci`. Each repo's
`.ci/docker/Dockerfile` adds only its repo-specific tools; argo-apps' layer adds
helm, kustomize, kubeconform, the CRDs-catalog, and the kryptos CLI.

GitLab triggers pipelines and reports commit status directly — no external
webhook, event source, or status-API round-trip.

## Pipeline shape (per repo)

Most jobs come from **GitLab CI/CD Components** published by the
`homelab/ci-components` project (the CI/CD Catalog hub). Each repo includes a
component by ref and passes typed `inputs:`:

```yaml
include:
  - component: source.example.com/homelab/ci-components/scan-secrets@2.0.0
```

Since ci-components 2.0.0 every component's `image` input defaults to the
consumer's `$CI_IMAGE` variable, so most includes need no `image:` line, and
the lint/scan components fall back to config defaults baked into ci-base at
`/opt/ci/config/` when no repo-local `.config/` rule file exists.

The catalog publishes `scan-secrets`, `lint-yaml`, `lint-shell`,
`lint-markdown`, `trivy-config`, `trivy-image`, `cosign-sign`, `sbom-attest`,
`mirror-github`, `ci-image`, `auto-tag`, `notify-discord`, and
`test-ci-scripts`. argo-apps' own `validate:apps` and
`validate:kryptos-configs` stay inline, since they are repo-specific. Stages run
fail-fast, gated by `rules:changes` so only relevant jobs run; argo-apps' stages
are:

```text
scan → lint → validate → image → mirror
```

- **`scan:secrets`** — gitleaks over full history, every MR + main push,
  unconditional (bypass-proof; catches secrets that slip past local hooks).
- **`scan:trivy-config`** (argo-apps) — `trivy config` misconfig scan over
  `apps/**`, gated to manifest changes. Console output plus a SARIF artifact;
  reads `.config/.trivyignore.yaml`. Report-only during shakeout, then blocks
  on HIGH/CRITICAL. Trivy is baked into the CI image; the job is the
  `trivy-config` component from `homelab/ci-components`, with the `apps`
  target and the `.config/.trivyignore.yaml` `ignorefile` input.
- **`lint:*`** — one job per tool (`yaml`, `shell`, `markdown`, each from its
  `lint-*` component), gated to its file types. Each reads the shared
  `.config/` rule files.
- **`validate:apps`** + **`validate:kryptos-configs`** — argo-apps' inline
  validation (see [per-repo validation](#per-repo-validation) below).
- **`image`** — `build:ci-image` (the `ci-image` component) then separate
  `sign:ci-image` (the `cosign-sign` component, cosign by digest) and
  `sbom:ci-image` (the `sbom-attest` component: syft SPDX SBOM attached as a
  cosign attestation) jobs. All three also fire on the scheduled rebuild
  pipeline (see [Scheduled jobs](#scheduled-jobs)).
- **`mirror`** — `mirror:github` (the `mirror-github` component), gated to the
  scheduled pipeline (see [Scheduled jobs](#scheduled-jobs)).

### Per-repo validation

<!-- markdownlint-disable MD013 -->

| Repo | Validation / build jobs |
| --- | --- |
| `argo-apps` | `validate:apps` — per changed app dir: `kustomize build --enable-helm \| kubeconform` against the baked CRDs-catalog (no cluster); `validate:kryptos-configs` — `kryptos validate` on the secret configs |
| `helm-charts` | `validate:charts` (helm lint → dep update → template); `publish:charts` (helm push → cosign sign → `crane delete` rollback) + Discord notify |
| `proxmox-infra` | `lint:terraform`/`lint:ansible`; `build:<image>` + `sign:<image>` ×4 (pihole, unbound, unbound-recursive, dnscrypt-proxy) |
| `kryptos` | `lint:go` + `test:go` + `smoke:cli`; `release` (goreleaser on `v*` tag); `auto-tag` (conventional-commit → next semver) |

<!-- markdownlint-enable MD013 -->

## Branch / event gating

A `workflow:rules` block at the top of each `.gitlab-ci.yml` dedupes pipelines:
**merge-request pipelines on branches, push pipelines only on `main`**, plus
`v*` tag pipelines (kryptos). Side-effecting jobs (publish, image build, sign,
release) carry main-push (or tag) rules, while read-only lint/validate/scan jobs
run on MRs too so a Renovate/feature MR gets a commit status before merge.

`rules:changes` then narrows each job to the files it cares about — a docs-only
MR runs `lint:markdown` + `scan:secrets` and skips the rest; an app-manifest MR
runs `validate:apps`; a `charts/*/Chart.yaml` bump on main runs
`publish:charts`. The pipeline graph shows exactly which checks ran.

pre-commit is **not** run in CI — it stays a local-only developer hook. The
equivalent checks run as the native CI jobs above, which is why the
security-relevant `scan:secrets` runs server-side unconditionally (local hooks
can be bypassed with `--no-verify`, web-UI edits, or Renovate commits).

## Scheduled jobs

Renovate and the GitHub mirror run as **GitLab pipeline schedules**
(Settings → CI/CD → Schedules).

- **Renovate** — centralized in the **`homelab/renovate`** project: a single
  daily schedule (03:00 Europe/Berlin) runs the upstream
  `renovate-bot/renovate-runner` template with
  `--autodiscover=true --autodiscover-filter=homelab/*`. Every repo carries
  only a `renovate.json` extending the shared preset
  (`local>homelab/renovate`); there are **no per-repo Renovate schedules or
  jobs**. Tokens come from the group `RENOVATE_*` CI/CD variables; the engine
  image and runner template ref are pinned (Renovate-tracked) in the
  `homelab/renovate` repo itself.
- **GitHub mirror** — one schedule per mirrored repo (argo-apps, helm-charts,
  proxmox-infra, ci-components; **not** kryptos), 04:00–04:20 Europe/Berlin,
  carrying `SCHEDULE_TYPE=mirror` which the `mirror:github` job gates on.
- **Image rebuild** — schedules carrying `SCHEDULE_TYPE=rebuild` trigger
  `build:ci-image` + `sign:ci-image` + `sbom:ci-image` without a Dockerfile
  change, so OS/base-layer CVE fixes land in the CI images (and get signed
  and attested) without a commit.

### GitHub mirror flow

```text
mirror:github job (mirror-github component, /opt/ci tooling from ci-base)
  -> python3 /opt/ci/publish_github.py --verbose
       sanitize_repo.py     .ci/sanitize/sanitize-config.yaml drives
                            replacement + exclude rules
       verify_sanitization.py   HARD GATE: exit 1 = blocked push
       git push --force github main
         (HTTPS, x-access-token:${GITHUB_TOKEN}@github.com/owner/repo)
```

The three Python scripts (`publish_github.py`, `sanitize_repo.py`,
`verify_sanitization.py`) live in `homelab/ci-components` and are baked into the
shared `ci-base` image at `/opt/ci/`. Every repo's `mirror:github` job (the
`mirror-github` component) runs them straight from `/opt/ci/` at runtime, so the
tooling is defined once and inherited by each thin per-repo CI image — there is
no per-repo copy and no sync step. Each repo keeps only its own
`.ci/sanitize/sanitize-config.yaml`, which the baked scripts read via the
`SOURCE_REPO` they operate on.

#### Token + sanitization config

`GITHUB_PUBLISH_TOKEN` (group CI/CD variable) is a fine-grained PAT with
contents:write on the target GitHub repos only; `publish_github.py` redacts it
from every logged URL. `<repo>/.ci/sanitize/sanitize-config.yaml` is layered:
it `extends` the shared base baked into ci-base at
`/opt/ci/config/sanitize-base.yaml` (common domain/name/path replacements,
exclusions, and verification terms) and adds only repo-specific entries. The
merge is union-only for the protective lists — a child config can add
exclusions and sensitive terms but never remove one from the base. The
flattened replacements (longest-first) are applied to every text file;
`exclude_patterns`/`exclude_dirs` drop secrets and caches;
`verification.additional_sensitive_terms` lists PAT prefixes the verifier
refuses to publish if found.

## Cosign signing

Every custom OCI artifact pushed to Harbor (CI images, Helm charts, the
proxmox-infra images) is cosign-signed immediately after upload, by digest:

```bash
cosign login "$HARBOR_HOST" -u "$HARBOR_USERNAME" --password-stdin
cosign signing-config create \
  --no-default-fulcio --no-default-rekor --no-default-tsa --no-default-oidc \
  --out /tmp/signing-config.json
cosign sign --yes --signing-config=/tmp/signing-config.json \
  --new-bundle-format --key "$COSIGN_KEY" "<ref>@<digest>"
```

The empty signing-config (no Fulcio/Rekor/TSA/OIDC) is the cosign-v3 way to
sign **without** a public-Rekor transparency-log entry: the cluster/runner
can't reach `rekor.sigstore.dev`, and for a private Harbor signed with a static
keypair the public log is meaningless — provenance is the key, verified
offline.

`COSIGN_KEY` is a **File-type** CI/CD variable, so `$COSIGN_KEY` is a *path* to
the key file — passed straight to `cosign --key "$COSIGN_KEY"` (never written
to a temp file). The public half is committed at `helm-charts/cosign.pub` for
offline verification (the `sign:ci-image` job verifies with
`--insecure-ignore-tlog=true`, the verify-side counterpart of not uploading a
tlog entry).

## Secrets (GitLab CI/CD variables)

Harbor auth comes from the **GitLab Harbor integration** on the `homelab`
group, which injects `$HARBOR_USERNAME` / `$HARBOR_PASSWORD` / `$HARBOR_HOST` /
`$HARBOR_URL` / `$HARBOR_OCI` / `$HARBOR_PROJECT` into every project's CI/CD.
Other secrets are CI/CD variables (masked + protected):

<!-- markdownlint-disable MD013 -->

| Variable | Scope | Used by |
| --- | --- | --- |
| `COSIGN_KEY` (File) + `COSIGN_PASSWORD` | group | cosign signing |
| `RENOVATE_TOKEN` + `RENOVATE_GITHUB_COM_TOKEN` + `DOCKER_HUB_*` | group | renovate |
| `GITHUB_PUBLISH_TOKEN` | group | GitHub mirror force-push |
| `KRYPTOS_RELEASE_TOKEN` | project: kryptos | goreleaser + auto-tag |
| `KRYPTOS_READ_TOKEN` | group | argo-apps CI-image kryptos fetch (BuildKit secret) |
| `DISCORD_WEBHOOK_URL` | project: helm-charts | chart-publish notify |

<!-- markdownlint-enable MD013 -->

CI needs no dedicated registry/clone secrets of its own: Harbor auth comes from
the group integration, GitLab clones natively via `CI_JOB_TOKEN`, and commit
status is native. The kryptos release token needs a `v*` **protected-tag** rule
(the release bot's role must be allowed to create it) or the protected variable
is withheld and goreleaser fails with a missing token.

## Per-app validate (argo-apps)

`validate:apps` is gated on `rules:changes:[apps/**]` (native). When it runs,
[`detect_apps.py`](../.ci/scripts/detect_apps.py) enumerates the changed app
dirs (a dynamic set native `rules` can't list), and the job loops
[`validate_app.py`](../.ci/scripts/validate_app.py) over each:

```text
kustomize build --enable-helm <dir> | kubeconform -strict -summary \
  -schema-location default -schema-location /opt/crds-catalog/... \
  -skip CustomResourceDefinition
```

kubeconform validates against the **datreeio CRDs-catalog baked into the CI
image** at `/opt/crds-catalog` — no cluster access needed. CRDs the catalog
doesn't cover are skipped per `validate_app.py`.

## Verifying a chart signature locally

<!-- markdownlint-disable MD013 -->

```bash
helm pull oci://registry.example.com/example-org/helm-charts/searxng --version 1.0.6
cosign verify \
  --key https://source.example.com/example-org/helm-charts/raw/branch/main/cosign.pub \
  --insecure-ignore-tlog=true \
  registry.example.com/example-org/helm-charts/searxng:1.0.6
```

<!-- markdownlint-enable MD013 -->

## Status

| Layer | Source of truth | Notes |
| --- | --- | --- |
| ArgoCD | GitLab (`main`) | All Applications + the `apps` ApplicationSet |
| GitLab CI | GitLab | One `.gitlab-ci.yml` per repo; native status |
| GitLab Runner | proxmox-infra | `gitlab-runner` LXC, Docker-socket executor |
| Harbor | Self-hosted | Registry + cosign signatures |
