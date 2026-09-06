# Security

This document covers security practices, secret management, authentication,
and TLS certificate handling for the platform.

## Table of Contents

- [Overview](#overview)
- [Secret Management](#secret-management)
- [SSO Architecture](#sso-architecture)
- [Cloudflare Access](#cloudflare-access-edge-authentication)
- [TLS Certificates](#tls-certificates)
- [CI/CD Security Scanning](#cicd-security-scanning)
- [Security Best Practices](#security-best-practices)

## Overview

The platform implements **defense-in-depth security** with multiple layers:

- 🔐 **Sealed Secrets** - Encrypted secrets in Git (safe to commit)
- 🔑 **Kryptos** - Enterprise-grade secret generation tool
- 🛡️ **SSO** - Centralized authentication with Authentik (Traefik ForwardAuth
  via its embedded outpost, and OIDC provider)
- 🔒 **TLS** - Automated certificate management with Let's Encrypt
- 🔍 **Security Scanning** - Multi-layer vulnerability detection in CI/CD

**Principle**: No plaintext secrets in Git, ever.

## Secret Management

### Sealed Secrets

**Technology**:
[Sealed Secrets Controller](https://github.com/bitnami-labs/sealed-secrets)
v0.35.0

**How It Works**:

1. **Encrypt** secret locally using `kubeseal` CLI
2. **Commit** encrypted SealedSecret to Git (safe)
3. **Deploy** via ArgoCD
4. **Decrypt** by controller in cluster → creates normal Secret

**Architecture**:

```text
graph LR
    A[Developer] -->|1. kubeseal| B[SealedSecret YAML]
    B -->|2. Git commit| C[Git Repository]
    C -->|3. ArgoCD sync| D[Kubernetes Cluster]
    D -->|4. Controller unseals| E[Secret]
    E -->|5. Pods consume| F[Application]

    style B fill:#4CAF50
    style E fill:#2196F3
```

**Encryption**: RSA 4096-bit public/private key pair

**Controller Location**: `kube-system` namespace (sync wave 0)

**Priority Class**: `critical-infrastructure` (never evicted)

### Sealed Secrets Controller Deployment

**Configuration**: [sealed-secrets/][sealed-secrets-dir]

[sealed-secrets-dir]: ../apps/infra/sealed-secrets/

**Installation Source**: GitHub releases (official manifests)

**Patches Applied**:

- `priorityClassName: critical-infrastructure`
- Node affinity for infrastructure tier
- Tolerations for control-plane taints

**Namespace**: `kube-system` (cluster-wide resource)

### Using kubeseal

**Install kubeseal**:

```bash
# macOS
brew install kubeseal

# Linux
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.35.0/kubeseal-<arch>-<os>
```

**Seal a Secret**:

```bash
# Fetch controller's public key
kubeseal --fetch-cert > pub-cert.pem

# Seal a secret
kubectl create secret generic my-secret \
  --from-literal=password=mysecretpass \
  --dry-run=client -o yaml | \
  kubeseal --cert pub-cert.pem --format yaml > my-sealed-secret.yaml
```

**Important**: Use Kryptos instead of manual `kubeseal` for most workflows.

### Kryptos Secret Management

**Technology**: Go-based CLI tool with interactive TUI

**Location**: [kryptos/](../kryptos/)

**Documentation**: [kryptos/README.md](../kryptos/README.md)

**Features**:

- ✅ **Interactive TUI** - User-friendly menu-driven interface
- ✅ **Auto-generation** - Secure passwords, API keys, passphrases
- ✅ **Template-based** - YAML configurations per app
- ✅ **Type support** - `Opaque` secrets + `kubernetes.io/dockerconfigjson`
- ✅ **Automatic sealing** - Calls `kubeseal` under the hood
- ✅ **Reflector integration** - Automatic annotations for namespace replication

#### Usage

```bash
kryptos   # released binary, run from the repo root
```

**Workflow**:

1. **Select app** from menu (e.g., "SearXNG")
2. **Select secret** to generate (e.g., "SearXNG Configuration")
3. **Enter values** or use auto-generation keywords
4. **SealedSecret generated** in `apps/<tier>/<app>/secrets/`

#### Auto-Generation Keywords

<!-- markdownlint-disable MD013 MD060 -->
| Keyword      | Output                     | Example                           |
| ------------ | -------------------------- | --------------------------------- |
| `secure`     | 32-char secure password    | `L9kT4xP2mN7qR5wV3zC8bF6jH1dG0sA` |
| `strong`     | 32-char password + symbols | `K!8m@4xP#7nT&2rV$9zC%3bF*1dG^0s` |
| `apikey`     | 64-char hex API key        | `a1b2c3d4e5f6...`                 |
| `passphrase` | 4-word passphrase          | `correct horse battery staple`    |
<!-- markdownlint-enable MD013 MD060 -->

#### Adding a New App

Create `kryptos/configs/<app>.yaml`:

```text
apiVersion: kryptos.dev/v1
kind: SecretConfig

metadata:
  name: "myapp"
  displayName: "My App"
  namespace: "myapp"

spec:
  secrets:
    - name: myapp-credentials
      displayName: "App Credentials"
      description: "Authentication credentials"
      type: Opaque
      fields:
        - name: username
          prompt: "Username"
          default: "admin"
          required: true

        - name: password
          prompt: "Password"
          generator: strong
          required: true
```

Run `kryptos` to generate the secret.

#### Docker Registry Secrets

Kryptos supports `kubernetes.io/dockerconfigjson` type:

```text
spec:
  secrets:
    - name: dockerhub-secret
      type: "kubernetes.io/dockerconfigjson"
      annotations:
        reflector.v1.k8s.emberstack.com/reflection-allowed: "true"
        reflector.v1.k8s.emberstack.com/reflection-auto-enabled: "true"
      fields:
        - name: username
          prompt: "Docker Hub Username"
        - name: password
          prompt: "Docker Hub Password/Token"
        - name: email
          prompt: "Email Address"
```

## SSO Architecture

Single Sign-On (SSO) provides **centralized authentication**. One stack is
live: **Authentik** (`auth.example.com`), deployed from
`apps/infra/authentik/`.

- Identity provider *and* ForwardAuth target in one: the **embedded outpost**
  inside `authentik-server` answers Traefik's ForwardAuth calls, so there is
  no separate auth proxy to run
- **`authentik-forwardauth`** Traefik middleware in the `authentik`
  namespace — the single middleware every protected app references
- Per-app authorization via a per-application **`admins` group binding** in
  the blueprints; a host with no application in the outpost gets a 404
  (deny-by-default equivalent), and a user outside `admins` is denied
- One Authentik session covers every protected app; MFA is enforced
  flow-wide in the default authentication flow, not per app

Authentik is also the **OIDC provider** for Headlamp (which forwards each
user's `id_token` to the Kubernetes API for per-user cluster RBAC), Omni,
and SnapOtter.

### Architecture Overview

```text
graph TB
    A[User Browser] -->|1. Request https://app.example.com| B[Traefik Ingress]
    B -->|2. ForwardAuth check| C[Outpost /outpost.goauthentik.io/auth/traefik]
    C -->|3. No valid session| D{Authenticated?}
    D -->|No| E[302 to the authorize flow on auth.example.com]
    E -->|4. Login + MFA| F[Authentik Portal]
    F -->|5. Session established| A
    A -->|6. Retry request| B
    B -->|7. Session valid, admins binding allows| G[Application]

    style F fill:#6A1B9A
    style C fill:#2196F3
    style G fill:#4CAF50
```

**Flow**:

1. User requests a protected app (e.g., `https://longhorn.example.com`)
2. Traefik invokes the `authentik-forwardauth` middleware, which calls the
   embedded outpost (`/outpost.goauthentik.io/auth/traefik` on the
   `authentik-server` Service)
3. The outpost matches the host to its per-app proxy provider
   (`forward_single` mode) and checks for a valid session
4. If no session → 302 towards the login flow, which runs through the app's
   own `/outpost.goauthentik.io/` route and the authorize URL on
   `auth.example.com` — this is why every gated IngressRoute carries a second,
   middleware-free outpost route
5. User authenticates; MFA is enforced by the default authentication flow
6. The outpost establishes the session and redirects back to the original URL
7. On the retried request the outpost validates the session **and** the
   application's `admins` group binding. Only then does the request reach
   the app, with `X-authentik-username` / `-groups` / `-email` / `-name` /
   `-uid` headers attached (no app currently consumes them).

Step 7 is the behavioural difference worth remembering: authentication and
authorization are separate. A valid session is not sufficient — a user
outside the `admins` group is denied by the application's policy binding,
and a host with no application at all gets a 404 from the outpost.

### Authentik (Identity Provider)

**Deployment**: `apps/infra/authentik/`

**Namespace**: `authentik`

**Database**: Shared PostgreSQL cluster
(`postgresql.postgresql.svc.cluster.local`, database `authentik`) — the only
backend; Authentik uses no Redis/Valkey

**UI**: `https://auth.example.com`

**Roles**:

- SSO portal for interactive login
- Traefik ForwardAuth provider via the embedded outpost
  (`/outpost.goauthentik.io/auth/traefik`)
- OIDC provider for Headlamp, Omni, and SnapOtter

**Users**, flows, and MFA enrolment are managed in the Admin UI. `akadmin`
is the break-glass admin; its password is `AUTHENTIK_BOOTSTRAP_PASSWORD` in
the sealed `authentik-secret`. There is no SMTP relay — password recovery
links are minted in the Admin UI (user → *View recovery link*).

**Config-as-code**: providers, applications, group bindings, and the outpost
assignment are declarative blueprints in
`apps/infra/authentik/blueprints/*.yaml`, mounted into the worker via the
`authentik-blueprints` ConfigMap (kustomize `configMapGenerator`, chart
value `blueprints.configMaps`):

- `00-groups.yaml` — the `admins` group
- `10-proxy-providers.yaml` — forward-auth proxy providers, applications,
  and the admins-only bindings
- `20-oauth2-providers.yaml` — OIDC providers and scope mappings
- `30-outpost.yaml` — embedded outpost provider assignment

**Credentials** are generated via Kryptos and stored as SealedSecrets
(`kryptos/configs/authentik.yaml`). `AUTHENTIK_SECRET_KEY` is **immutable** —
it signs cookies and derives unique IDs; losing it invalidates every
session. OIDC client secrets live in the `authentik-oidc-clients` secret and
are read by the blueprints via `!Env` from the worker environment.

### Protecting an Application with SSO

Gating a host takes **four pieces**, all in Git and order-safe — the outpost
fails closed (404) until the blueprint side exists.

**Piece 1**: A proxy provider, application, and `admins` policy binding in
[blueprints/10-proxy-providers.yaml][proxy-blueprint]. Copy an existing
trio; the essentials are:

```text
- model: authentik_providers_proxy.proxyprovider
  attrs:
    mode: forward_single
    external_host: https://myapp.example.com
    authorization_flow: !Find [authentik_flows.flow,
      [slug, default-provider-authorization-implicit-consent]]
    invalidation_flow: !Find [authentik_flows.flow,
      [slug, default-provider-invalidation-flow]]
- model: authentik_core.application        # slug: myapp
- model: authentik_policies.policybinding  # group: admins
```

**Piece 2**: Add the provider to the embedded outpost's `providers` list in
[blueprints/30-outpost.yaml][outpost-blueprint].

**Piece 3 + 4**: The `authentik-forwardauth` middleware on the app's
IngressRoute, plus a second route on the same IngressRoute forwarding the
outpost's own endpoints (login redirect target, callback) — **no**
middleware; the longer rule wins Traefik's default priority:

```text
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: myapp-ingressroute
  namespace: myapp
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`myapp.example.com`)
      kind: Rule
      middlewares:
        - name: authentik-forwardauth
          namespace: authentik
      services:
        - name: myapp
          port: 80
    - match: Host(`myapp.example.com`) && PathPrefix(`/outpost.goauthentik.io/`)
      kind: Rule
      services:
        - kind: Service
          name: authentik-server
          namespace: authentik
          port: 80
```

[proxy-blueprint]: ../apps/infra/authentik/blueprints/10-proxy-providers.yaml
[outpost-blueprint]: ../apps/infra/authentik/blueprints/30-outpost.yaml

The middleware lives in the `authentik` namespace rather than `traefik`; the
cross-namespace reference works because Traefik runs with
`providers.kubernetesCRD.allowCrossNamespace: true`.

How it behaves:

- ForwardAuth on every request to `/outpost.goauthentik.io/auth/traefik`
- Valid session **and** membership in `admins` → 200, request proceeds with
  `X-authentik-username`, `-groups`, `-email`, `-name`, `-uid` injected
- No session → 302 into the login flow on `auth.example.com`
- Valid session but user **not in `admins`** → denied by the policy binding
- Host with **no application** in the outpost → 404. This is the fail-closed
  default; it looks broken but means Piece 1 or 2 is missing.

Deploy, sync, and test in a **fresh private window**. Browse to
`myapp.example.com` unauthenticated; expect a redirect that completes on
`auth.example.com`, authenticate, then land back on the app. Subsequent
visits to other protected apps reuse the same session — no re-login.

To audit which routes are gated:

```bash
grep -rn "authentik-forwardauth" apps/ --include="*.yaml"
```

#### SSO in front of an app that has its own login

For an app that already authenticates its own users but is published externally
(via the Cloudflare tunnel), the SSO middleware can be layered as a second,
edge gate — reached only over the tunnel — while the LAN keeps single-login.
Do this with **two hostnames**, since the tunnel routes by `Host` to Traefik and
cannot distinguish LAN vs external for one host:

- an internal host (LAN-only, no middleware) for the app's built-in login, and
- a separate external host carrying the `authentik-forwardauth` middleware,
  which is the only host published as a tunnel public hostname.

Open WebUI uses this pattern: `open-webui.example.com` (LAN, built-in login) plus
`chat.example.com` (tunnel, Authentik SSO **in addition to** the built-in login).
See `apps/user/open-webui/ingress/ingressroute.yaml`.

An app that authenticates its own users and is *not* tunnel-exposed does not
need a ForwardAuth gate at all — ArgoCD, Harbor, Headlamp and Komodo all sit
on their own login.

**Apps with internal auth disabled (e.g. Open WebUI's `WEBUI_AUTH=false`):**
when an app's own authentication is turned off and the `authentik-forwardauth`
middleware is the sole gate, treat the IngressRoute middleware reference as
load-bearing — removing it exposes the app to unauthenticated traffic. Add a
comment on the IngressRoute to flag this, and remember the paired blueprint
application (with its `admins` binding) is equally load-bearing.

### Gated Routes

All seven ForwardAuth gates are admins-only; MFA comes from the flow, not
per app.

<!-- markdownlint-disable MD013 -->
| Route | Gate |
| --- | --- |
| `longhorn.example.com` | `authentik-forwardauth` — Longhorn has no auth of its own |
| `privatebin.example.com` | `authentik-forwardauth` — no own auth, public via the tunnel |
| `translate.example.com` | `authentik-forwardauth` — no own auth, external LXC |
| `chat.example.com` | `authentik-forwardauth` (+ built-in login; tunnel host) |
| `docuseal.example.com` | `authentik-forwardauth` (+ built-in login) |
| `memos.example.com` | `authentik-forwardauth` (+ built-in login) |
| `pdf.example.com` | `authentik-forwardauth` (+ built-in login) |
| `komodo.example.com` | Komodo's own login — **no** ForwardAuth |
| `headlamp.example.com` | Authentik **OIDC** (not ForwardAuth) |
<!-- markdownlint-enable MD013 -->

Komodo sits off ForwardAuth deliberately: it authenticates its own users, so
it follows the same pattern as ArgoCD, Harbor and Headlamp. With nothing
gated, its IngressRoute is a single catch-all rule. Note that its `/listener`
GitLab webhook path needs a dedicated higher-priority route to bypass auth if
a gate is ever added — without that carve-out, CI webhooks fail silently.

### Kubernetes API Authentication

Headlamp authenticates against Authentik's `headlamp` OIDC client and
forwards the resulting `id_token` to the apiserver. The binding at
`apps/services/headlamp/base/oidc-admin-binding.yaml` maps the `oidc:admins`
group to `cluster-admin` (Authentik group `admins` → claim `admins` →
prefixed `oidc:admins`).

The apiserver uses structured `AuthenticationConfiguration` (stable since
Kubernetes 1.34) from `machine.files` in
`proxmox-infra ansible/talos/patches/controlplane.yaml` — there are no
`--oidc-*` flags. It trusts exactly one issuer,
`https://auth.example.com/application/o/headlamp/` (Authentik issuers are per
application, with the trailing slash — the bare hostname is **not** an
issuer), with audience `headlamp`; `claimMappings` set `username` from
`preferred_username` (prefix `oidc:`) and `groups` from `groups` (prefix
`oidc:`).

Changing that file **cannot** apply in Talos immediate mode — stage it
(`talosctl edit machineconfig --mode staged`) and reboot control planes one
at a time. Never run a blind full `make apply-configs`: the repo's
`kubernetes_version` can lag the live cluster and `talosctl apply` would
downgrade it — always `--dry-run` first.

**Break-glass**: the cert-based kubeconfig at
`proxmox-infra ansible/talos/configs/kubeconfig` authenticates as `admin` in
`system:masters` over X509, independent of any identity provider. It stays
usable when Authentik is down.

#### Adding an OIDC client to Authentik

OIDC providers, applications, and scope mappings are blueprints in
`apps/infra/authentik/blueprints/20-oauth2-providers.yaml`. The issuer is
**per application** — `https://auth.example.com/application/o/<slug>/` — and
three settings are non-obvious. All are already applied to the existing
clients (headlamp, omni, snapotter).

**1. `grant_types` must be set explicitly.** An `oauth2provider` blueprint
that omits `grant_types` persists an **empty list**, and every authorize
request is then rejected with `invalid_request`.

**2. There is no built-in `groups` scope.** The blueprint defines a custom
`groups` scope mapping; clients that need group claims (Headlamp) request
the scope explicitly.

**3. `email_verified` must be asserted.** The stock email mapping reports
`email_verified: false` (since 2025.10), and Omni rejects unverified emails
— so the blueprint carries a custom email mapping asserting
`email_verified: true`.

PKCE is client-initiated: Authentik has no `require_pkce` toggle. Headlamp
initiates S256 itself.

**Client secrets** are plaintext values in the `authentik-oidc-clients`
SealedSecret — the single source of truth. Blueprints read them via `!Env`
from the worker environment; consumers derive the same value
(headlamp/snapotter via kryptos `cluster_secret` derive; omni is mirrored
manually to the proxmox-infra Ansible vault).

**Signing key**: the "authentik Self-signed Certificate" keypair signs
`id_token`s. Rotating it changes the JWKS; consumers refetch it via OIDC
discovery.

**Diagnosing**: blueprint application status is in the Admin UI →
Customization → Blueprints (or the worker logs) — a failed blueprint shows
"error" on the instance; pods do not crash. Token *rejection* is recorded in
the **apiserver** logs
(`kubectl -n kube-system logs kube-apiserver-talos-cp-1`), not by Authentik.

## Cloudflare Access (Edge Authentication)

Cloudflare Access authenticates tunnel traffic **at Cloudflare's edge**, before
it reaches the tunnel or Traefik. It is a second, outer gate in front of
Authentik — not a replacement for it.

### What the Tunnel Actually Publishes

The tunnel runs in **managed** mode (`managed.enabled: true` in
[cloudflared values.yaml](../apps/infra/cloudflared/values.yaml)), so its
hostname routing is configured in the Cloudflare Zero Trust dashboard and is
**not in this repo**. Most `*.example.com` IngressRoutes are LAN-only; only the
hostnames below are reachable from the internet.

Read the live routing from the tunnel client rather than inferring it from
IngressRoutes:

```bash
kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared \
  | grep "Updated to new configuration"
```

| Published host | Origin gate | Access policy |
| --- | --- | --- |
| `chat.example.com` | `authentik-forwardauth` + built-in login | Gate |
| `memos.example.com` | `authentik-forwardauth` | Gate |
| `privatebin.example.com` | `authentik-forwardauth` | Gate |
| `translate.example.com` | `authentik-forwardauth` | Gate |
| `auth.example.com` | none — it *is* the IdP | **Never gate** |
| `plex.example.com` | Plex's own login | Leave open |
| `seerr.example.com` | Overseerr's own login | Leave open |
| `litellm-ext.example.com` | scoped virtual API key | Leave open |

### Why `auth.example.com` Must Stay Open

The gated hosts redirect unauthenticated browsers into a login flow that
completes on `auth.example.com`. Putting Access in front of the IdP makes
satisfying that redirect require a login that itself requires the redirect —
a loop that locks out every SSO app at once. The round-trip is a top-level
browser navigation, so it completes normally while the IdP host is un-gated.

Verify the redirect still works after any Access change:

```bash
curl -sS -o /dev/null -w '%{http_code} -> %{redirect_url}\n' \
  https://memos.example.com/
# expect: 302 towards the authorize URL on auth.example.com
# (…/application/o/authorize/…); an unknown host returns 404
```

### Access Does Not Cover the LAN

The tunnel routes by `Host` header and cannot distinguish LAN from external
traffic for the same hostname. A LAN client resolving these hosts internally
reaches Traefik directly and never passes through Cloudflare. **Access hardens
the external path only** — the `authentik-forwardauth` middleware on each
IngressRoute stays load-bearing and must not be removed.

### Adding an Access Application

Per gated host, in Cloudflare Zero Trust → Access → Applications:

1. **Add an application** → *Self-hosted*.
2. **Application domain**: the exact hostname (e.g. `memos.example.com`).
3. **Session duration**: pick a lifetime no longer than the Authentik
   session; a longer Access session silently becomes the effective one.
4. **Policy**: action *Allow*, rule *Emails* → your address. Prefer an explicit
   email list over *Everyone* + IdP, which admits anyone that IdP will
   authenticate.
5. Save, then test in a private window **before** closing the working session.

Repeat for `chat`, `memos`, `privatebin`, `translate`. Do **not** create one
for `auth.example.com`.

### Lockout Recovery

An Access policy that rejects you locks out the external path for that host.
The config lives in Cloudflare, so recovery is from the dashboard, not the
cluster — deleting the Access application restores the previous behaviour
immediately. LAN access is unaffected and is the reliable fallback.

## TLS Certificates

### cert-manager

**Technology**: [Jetstack cert-manager](https://cert-manager.io/) v1.19.3

**Deployment**: `apps/infra/cert-manager/`

**Namespace**: `cert-manager`

**Priority Class**: `critical-infrastructure`

**Components**:

- `cert-manager-controller` - Certificate lifecycle management
- `cert-manager-webhook` - Validating webhook for CRDs
- `cert-manager-cainjector` - CA bundle injection

### Let's Encrypt Integration

**Challenge Method**: DNS01 (Cloudflare)

**Why DNS01?**:

- ✅ Works for wildcard certificates (`*.example.com`)
- ✅ No port 80/443 exposure required
- ✅ Supports internal services

**ClusterIssuers**:

```text
# Production
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: maintainer@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - dns01:
          cloudflare:
            apiTokenSecretRef:
              name: cloudflare-api
              key: api-token
        selector:
          dnsZones:
            - example.com
```

**Staging Issuer**: `letsencrypt-staging` (for testing)

### Cloudflare API Token

**SealedSecret**:
`apps/infra/cert-manager/secrets/cloudflare-api.yaml`

**Generate via Kryptos**:

```bash
kryptos   # released binary, run from the repo root
# Select: cert-manager → Cloudflare API Token
```

**Required Permissions**:

- Zone: DNS: Edit
- Zone: Zone: Read

### Wildcard Certificate

**Certificate Resource**:

```text
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: wildcard-example-com
  namespace: traefik
spec:
  secretName: wildcard-example-com-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - "*.example.com"
    - "example.com"
```

**Usage in IngressRoute**:

```text
spec:
  tls:
    secretName: wildcard-example-com-tls
```

**Auto-renewal**: cert-manager renews certificates 30 days before expiry

### DNS01 Challenge Process

```text
graph TB
    A[cert-manager] -->|1. Request cert| B[Let's Encrypt]
    B -->|2. Challenge: _acme-challenge TXT record| A
    A -->|3. Create DNS record| C[Cloudflare API]
    C -->|4. DNS propagation| D[Cloudflare DNS]
    B -->|5. Verify TXT record| D
    D -->|6. Record exists| B
    B -->|7. Issue certificate| A
    A -->|8. Store in Secret| E[wildcard-example-com-tls]

    style B fill:#FF9800
    style C fill:#F4511E
    style E fill:#4CAF50
```

**Verification**:

```bash
# Check certificate status
kubectl get certificate -n traefik

# Describe certificate (shows challenge status)
kubectl describe certificate wildcard-example-com -n traefik

# Check DNS record
dig _acme-challenge.example.com TXT
```

## CI/CD Security Scanning

The `argo-apps` pipeline runs two security-scan jobs in the `scan` stage. See
[CI-CD-PIPELINE.md](CI-CD-PIPELINE.md) for the full pipeline shape. Tool
versions are pinned in the CI image
([`.ci/docker/Dockerfile`](../.ci/docker/Dockerfile)) and bumped by Renovate.

<!-- markdownlint-disable MD013 MD060 -->
| Job | Tool | Scope | Purpose |
| --- | --- | --- | --- |
| `scan:secrets` | Gitleaks | Full git history, every MR + main push | Hardcoded secrets, bypass-proof |
| `scan:trivy-config` | Trivy `config` | `apps/**` manifests, on change | Kubernetes/Kustomize misconfiguration |
<!-- markdownlint-enable MD013 MD060 -->

**Output**: console logs plus a SARIF artifact (`trivy-config.sarif`,
7-day retention). Harbor performs additional server-side image vulnerability
scanning on push for images pushed to the registry.

**Failure**: `scan:secrets` always blocks on any finding. `scan:trivy-config`
starts report-only (`TRIVY_EXIT_CODE: "0"`) during its shakeout cycle; once
findings are triaged into [`.config/.trivyignore`](../.config/.trivyignore) the
override is removed and it blocks on HIGH/CRITICAL misconfigurations.

Container-image and Helm-chart scanning live in the repos that build those
artifacts (`example-org/helm-charts`, `example-org/proxmox-infra`), not here —
`argo-apps` builds no application images.

## Security Best Practices

### Secret Hygiene

✅ **DO**:

- Use Kryptos for all secret generation
- Commit only SealedSecrets to Git
- Use auto-generation keywords (`secure`, `strong`, `apikey`)
- Rotate secrets regularly (every 90 days recommended)
- Use separate secrets per environment (if applicable)

❌ **DON'T**:

- Commit plaintext secrets (even in comments)
- Use weak passwords manually
- Share secrets across multiple apps
- Store secrets in ConfigMaps (use Secrets instead)
- Hardcode secrets in Dockerfiles or code

### Authentication

✅ **DO**:

- Enable SSO for all user-facing apps via the `authentik-forwardauth`
  middleware, paired with a blueprint application + `admins` binding and the
  outpost route
- Use strong client and session secrets (Kryptos `strong`/`apikey`)
- Use HTTPS for all endpoints
- Rotate the OIDC client secrets in `authentik-oidc-clients` periodically
  (consumers derive the same value — reseal both sides together)

❌ **DON'T**:

- Expose apps without authentication
- Use HTTP (always HTTPS via Traefik)
- Reuse the same OIDC client secret across unrelated apps
- Commit plaintext OIDC client/cookie secrets — always seal via Kryptos

### TLS Certificate Best Practices

✅ **DO**:

- Use Let's Encrypt production issuer
- Enable auto-renewal (cert-manager handles this)
- Use wildcard certs for convenience
- Monitor certificate expiry (cert-manager alerts)
- Use Cloudflare proxy mode for DDoS protection

❌ **DON'T**:

- Use self-signed certificates in production
- Expose port 80 (HTTP) without redirect
- Hardcode certificate secrets
- Manually renew certificates (cert-manager automates)

### Network Security

✅ **DO**:

- Use Traefik IngressRoute (not standard Ingress)
- Enable Cloudflare Tunnel for external access
- Use NetworkPolicies for pod-to-pod isolation (future)
- Restrict external services to Traefik only
- Use MetalLB for L2 load balancing

❌ **DON'T**:

- Expose services via NodePort (use LoadBalancer)
- Allow direct pod access without ingress
- Trust user input (validate in apps)
- Run privileged containers (unless absolutely necessary)

### Priority Classes

✅ **DO**:

- Use `critical-infrastructure` for platform components
- Use `high-priority-stateful` for databases/caches
- Use `normal-priority` for stateless apps
- Document priority class usage in values.yaml

❌ **DON'T**:

- Use `critical-infrastructure` for applications
- Skip priority class assignment (defaults to normal-priority)

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - GitOps architecture and patterns
- [CI-CD-PIPELINE.md](CI-CD-PIPELINE.md) - Full CI/CD pipeline details
- [APPLICATIONS.md](APPLICATIONS.md) - Application catalog
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md) - Infrastructure components
- [kryptos/README.md](../kryptos/README.md) -
  Kryptos usage guide
- [Authentik blueprints](../apps/infra/authentik/blueprints/) -
  Declarative providers, applications, group bindings, and the outpost
- [Authentik ForwardAuth middleware](../apps/infra/authentik/middleware.yaml) -
  Traefik ForwardAuth wiring (`authentik-forwardauth`)
