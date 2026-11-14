# Security

This document covers security practices, secret management, authentication,
and TLS certificate handling for the platform.

## Table of Contents

- [Overview](#overview)
- [Exposure Model](#exposure-model)
- [Secret Management](#secret-management)
- [SSO Architecture](#sso-architecture)
- [Cloudflare Access](#cloudflare-access-edge-authentication)
- [TLS Certificates](#tls-certificates)
- [CI/CD Security Scanning](#cicd-security-scanning)
- [Security Best Practices](#security-best-practices)

## Overview

The platform implements **defense-in-depth security** with multiple layers:

- 🔐 **External Secrets + HashiCorp Vault** - values live in Vault; Git
  holds only `ExternalSecret` references
- 🛡️ **SSO** - Centralized authentication with Authentik (Traefik ForwardAuth
  via its embedded outpost, and OIDC provider)
- 🔒 **TLS** - Automated certificate management with Let's Encrypt
- 🔍 **Security Scanning** - Multi-layer vulnerability detection in CI/CD

**Principle**: No plaintext secrets in Git, ever.

## Exposure Model

Every app has one name, `<app>.example.com`. Whether it is reachable from the
internet is decided by which Traefik entrypoint carries a route for it, not by
the name.

<!-- markdownlint-disable MD013 -->
| Entrypoint | Service / IP | Who reaches it | Routes on it | Gates |
| --- | --- | --- | --- | --- |
| `lan` (+ `lan-http` → redirect) | `traefik-lan`, 10.140.0.60 | LAN clients (Technitium points every `*.example.com` name here) | every app | none — the LAN is the boundary; apps keep their own login |
| `public` (+ `public-http` → redirect) | `traefik`, ClusterIP only, no LAN address | the Cloudflare tunnel | public apps only | Cloudflare Access and/or Authentik |
<!-- markdownlint-enable MD013 -->

- The tunnel's origin is `public`, which has no LoadBalancer address, so a
  route bound only to `lan` cannot be reached from the internet, and a LAN
  client cannot reach `public` at all and never meets its gates.
- A public app with a gate needs **two IngressRoute objects** for the same
  host, because an IngressRoute has one `entryPoints` list: an ungated one on
  `lan` and a gated one on `public` (see
  `apps/user/opengist/ingress/ingressroute.yaml`). A public app without a
  Traefik gate lists both entrypoints in one IngressRoute (`auth`, `secret`,
  `plex`, `seerr`, `pdf`).
- Public apps: `auth`, `docuseal`, `gist`, `privatebin`,
  `translate`, `pdf`, `secret`, `plex`, `seerr`
  ([table](#what-the-tunnel-actually-publishes)). Everything else is LAN-only.
- Public DNS has only the tunnel hostnames, `wg` and ACME TXT records; the
  local Technitium `example.com` zone has an A record → 10.140.0.60 for every
  app.
- Apps that sign in through Authentik OIDC (Headlamp,
  Stirling-PDF, Semaphore) keep it on both entrypoints.
  New LAN-only apps use local auth or none — never an Authentik provider.
- The UniFi zone policies *User→Servers Traefik 80,443*, *Core→Servers git
  443* and *IoT→Servers* allow 10.140.0.60 on 80/443, and the Formuler
  reaches Plex on Unraid directly (*IoT→Storage*).
- Traefik reaches Unraid (Storage zone) only on the ports in the `unraid_apps`
  port group (proxmox-infra `terraform/unifi/groups.tf`). A new
  `external-services` endpoint on Unraid needs its port added there, or the
  route returns 502/504.
- The full address plan, zone matrix and DNS/DHCP layout:
  [proxmox-infra `docs/NETWORK.md`][network-doc].

[network-doc]: https://source.example.com/example-org/proxmox-infra/-/blob/main/docs/NETWORK.md

## Secret Management

### External Secrets and HashiCorp Vault

Every app Secret comes from the External Secrets Operator
(`apps/infra/external-secrets`, wave 0). An app keeps an `ExternalSecret` in
`apps/<tier>/<app>/secrets/`; ESO builds the Secret from HashiCorp Vault,
`kv/k8s/<namespace>/<secret>`, through the ClusterSecretStore `vault`. The
values live in Vault (proxmox-infra `docs/VAULT.md`), never in Git.

ESO logs in with Vault's `kubernetes` auth method, role `eso` (read-only on
`kv/k8s/*`). When Vault is sealed, existing Secrets stay as they are; only
updates and new Secrets wait for the unseal.

### Adding a Secret

1. Write the values into Vault. Read each value from stdin (`key=-`), so
   it never lands on a command line or in shell history:

   ```bash
   vault kv put -mount=kv k8s/<namespace>/<secret> password=-
   vault kv patch -mount=kv k8s/<namespace>/<secret> api-key=-   # add a field
   ```

2. Add `apps/<tier>/<app>/secrets/<secret>-external-secret.yaml` and list it
   in the app's `kustomization.yaml`:

   ```yaml
   apiVersion: external-secrets.io/v1
   kind: ExternalSecret
   metadata:
     name: myapp-secret
     namespace: myapp
   spec:
     refreshInterval: 1h
     secretStoreRef:
       kind: ClusterSecretStore
       name: vault
     target:
       name: myapp-secret
       creationPolicy: Owner
     dataFrom:
       - extract:
           key: k8s/myapp/myapp-secret
   ```

- `dataFrom.extract` copies every field of the app's own entry.
- A value another app owns (the database password in
  `kv/k8s/postgresql/<app>-db-secret`, the Valkey password in
  `kv/k8s/valkey/valkey-auth`) is read with `data[].remoteRef`
  (`key` + `property`), never copied into a second entry.
- A rendered value (a DSN) or a Secret that needs labels uses
  `target.template` with `engineVersion: v2` and `mergePolicy: Merge`; the
  default `Replace` drops every key the template does not list.
- `creationPolicy: Owner` adopts an unowned Secret of the same name and
  refuses one that another controller owns.

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
user's `id_token` to the Kubernetes API for per-user cluster RBAC),
Stirling-PDF and Semaphore.

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

1. User requests a protected app (e.g., `https://gist.example.com`)
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
- OIDC provider for Headlamp, Stirling-PDF, and Semaphore

**Users**, flows, and MFA enrolment are managed in the Admin UI. `akadmin`
is the break-glass admin; its password is `AUTHENTIK_BOOTSTRAP_PASSWORD` in
the `authentik-secret` (Vault `kv/k8s/authentik/authentik-secret`). There is
no SMTP relay — password recovery links are minted in the Admin UI (user →
*View recovery link*).

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

**Credentials** are ExternalSecrets from Vault
(`kv/k8s/authentik/<secret>`). `AUTHENTIK_SECRET_KEY` is **immutable** —
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
    - public
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
(via the Cloudflare tunnel), the SSO middleware is layered as a second, edge
gate on the public entrypoint only, while the LAN keeps single-login. Use
**one hostname in two IngressRoute objects**:

- `entryPoints: [lan]`, no middleware, for the app's built-in login, and
- `entryPoints: [public]` carrying the `authentik-forwardauth` middleware
  and the `/outpost.goauthentik.io/` route; only this one is reachable through
  the tunnel.

OpenGist uses this pattern for `gist.example.com`
(`apps/user/opengist/ingress/ingressroute.yaml`); so do privatebin, docuseal
and translate.

LAN-only apps carry no ForwardAuth gate at all — ArgoCD, Harbor, Headlamp,
Komodo, ntfy and Docmost sit on their own login.

**Apps without their own authentication (e.g. PrivateBin):**
when an app has no login of its own and the `authentik-forwardauth`
middleware is the sole gate, treat the IngressRoute middleware reference as
load-bearing — removing it exposes the app to unauthenticated traffic. Add a
comment on the IngressRoute to flag this, and remember the paired blueprint
application (with its `admins` binding) is equally load-bearing.

### Gated Routes

All four ForwardAuth gates sit on the `public` route of a public host and
are admins-only; MFA comes from the flow, not per app. The `lan` route of the
same host has no gate.

<!-- markdownlint-disable MD013 -->
| Route | Gate on `public` (tunnel) |
| --- | --- |
| `privatebin.example.com` | `authentik-forwardauth` — no own auth |
| `translate.example.com` | `authentik-forwardauth` — no own auth, Unraid container |
| `gist.example.com` | `authentik-forwardauth` (+ built-in login) |
| `docuseal.example.com` | `authentik-forwardauth` (+ built-in login) |
| `pdf.example.com` | Authentik **OIDC** app login, no ForwardAuth; password login disabled |

| LAN-only route | Login |
| --- | --- |
| `longhorn.example.com`, `traefik.example.com`, `prometheus.example.com`, `alertmanager.example.com` | none — no auth of their own |
| `grafana.example.com` | built-in login (`grafana-admin`) |
| `loki.example.com` | push path only, Traefik basic auth (`loki-push-auth`) |
| `komodo.example.com`, `docmost.example.com` | built-in login |
| `obsidian.example.com` | image basic auth |
| `couchdb.example.com` | CouchDB basic auth (Obsidian LiveSync; never published) |
| `headlamp.example.com` | Authentik **OIDC** (Kubernetes RBAC) |
| `semaphore.example.com` | Authentik **OIDC** (password form hidden, but 2.19 still accepts the local admin password over the API until 2.20) |
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
clients (headlamp, stirling-pdf, semaphore).

**1. `grant_types` must be set explicitly.** An `oauth2provider` blueprint
that omits `grant_types` persists an **empty list**, and every authorize
request is then rejected with `invalid_request`.

**2. There is no built-in `groups` scope.** The blueprint defines a custom
`groups` scope mapping; clients that need group claims (Headlamp)
request the scope explicitly.

**3. `email_verified` must be asserted.** The stock email mapping reports
`email_verified: false` (since 2025.10), and clients that gate on it reject
the login — so the blueprint carries a custom email mapping asserting
`email_verified: true`.

PKCE is client-initiated: Authentik has no `require_pkce` toggle. Headlamp
initiates S256 itself.

**Client secrets** are plaintext values in Vault,
`kv/k8s/authentik/authentik-oidc-clients` — the single source of truth.
Blueprints read them via `!Env` from the worker environment; headlamp
and stirling-pdf read the same Vault entry through their ExternalSecrets.
Semaphore runs outside the cluster: its copy lives in proxmox-infra's
`kv/proxmox-infra/semaphore` (`oidc_client_secret`), so a rotation must
update both.

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
**not in this repo**. Only the hostnames below are reachable from the internet,
and only through their `public` routes; every other route lives on the
`lan` entrypoint, which the tunnel's origin never serves.

Read the live routing from the tunnel client rather than inferring it from
IngressRoutes:

```bash
kubectl logs -n cloudflared -l app.kubernetes.io/name=cloudflared \
  | grep "Updated to new configuration"
```

<!-- markdownlint-disable MD013 -->
| Published host | Origin gate | Access policy |
| --- | --- | --- |
| `gist.example.com` | `authentik-forwardauth` | Gate |
| `privatebin.example.com` | `authentik-forwardauth` | Gate |
| `translate.example.com` | `authentik-forwardauth` | Gate |
| `auth.example.com` | none — it *is* the IdP | **Never gate** |
| `plex.example.com` | Plex's own login | No Access app; a Cloudflare rule allows Serbia only (family access) |
| `seerr.example.com` | Overseerr's own login | No Access app; a Cloudflare rule allows Serbia only (family access) |
| `secret.example.com` | Onetime Secret's own login for creating secrets | Leave open — secret links are opened by outsiders |
<!-- markdownlint-enable MD013 -->

A request to `plex` or `seerr` from outside Serbia gets a Cloudflare `403`
(`server: cloudflare`, no Access redirect) — that is the country rule, not a
fault. Look the Ray ID up under Security → Events to confirm.

### Why `auth.example.com` Must Stay Open

The gated hosts redirect unauthenticated browsers into a login flow that
completes on `auth.example.com`. Putting Access in front of the IdP makes
satisfying that redirect require a login that itself requires the redirect —
a loop that locks out every SSO app at once. The round-trip is a top-level
browser navigation, so it completes normally while the IdP host is un-gated.

Verify the redirect still works after any Access change:

```bash
curl -sS -o /dev/null -w '%{http_code} -> %{redirect_url}\n' \
  https://gist.example.com/
# expect: 302 towards the authorize URL on auth.example.com
# (…/application/o/authorize/…); an unknown host returns 404
```

### Access Does Not Cover the LAN

A LAN client resolves every name through Technitium straight to the `lan`
entrypoint (10.140.0.60) and never passes through Cloudflare or the
ForwardAuth gate. **Access hardens the external path only** — the
`authentik-forwardauth` middleware on each `public` route stays
load-bearing and must not be removed. A LAN client that uses a public DNS
resolver (e.g. browser DNS-over-HTTPS) goes out through the tunnel instead and
meets the gates.

### Adding an Access Application

Per gated host, in Cloudflare Zero Trust → Access → Applications:

1. **Add an application** → *Self-hosted*.
2. **Application domain**: the exact hostname (e.g. `gist.example.com`).
3. **Session duration**: pick a lifetime no longer than the Authentik
   session; a longer Access session silently becomes the effective one.
4. **Policy**: action *Allow*, rule *Emails* → your address. Prefer an explicit
   email list over *Everyone* + IdP, which admits anyone that IdP will
   authenticate.
5. Save, then test in a private window **before** closing the working session.

Repeat for `gist`, `privatebin`, `translate`. Do **not** create one
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

**ExternalSecret**:
`apps/infra/cert-manager/secrets/cloudflare-api-external-secret.yaml`, from
Vault `kv/k8s/cert-manager/cloudflare-api`.

**Rotate**: write the new token from stdin, then let ESO refresh (1h) or
force it:

```bash
vault kv patch -mount=kv k8s/cert-manager/cloudflare-api api-token=-
kubectl -n cert-manager annotate externalsecret cloudflare-api \
  force-sync="$(date +%s)" --overwrite
```

**Required Permissions**:

- Zone: DNS: Edit
- Zone: Zone: Read

### Wildcard Certificate

**Certificate Resource**:

`apps/infra/traefik/certificates/certificate-prod.yaml`:

```text
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: example-com-wildcard-cert
  namespace: traefik
spec:
  secretName: example-com-wildcard-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - "example.com"
    - "*.example.com"
```

**Usage**: no IngressRoute sets `tls.secretName`. Traefik's default `TLSStore`
(`apps/infra/traefik/values.yaml`) serves `example-com-wildcard-tls` on every
TLS entrypoint, `public` and `lan` alike.

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
    A -->|8. Store in Secret| E[example-com-wildcard-tls]

    style B fill:#FF9800
    style C fill:#F4511E
    style E fill:#4CAF50
```

**Verification**:

```bash
# Check certificate status
kubectl get certificate -n traefik

# Describe certificate (shows challenge status)
kubectl describe certificate example-com-wildcard-cert -n traefik

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
blocks on HIGH/CRITICAL misconfigurations; accepted findings live in
[`.config/.trivyignore.yaml`](../.config/.trivyignore.yaml), each with a
statement.

`trivy:ci-image` scans this repo's own CI image after each rebuild. A
CRITICAL CVE fails the pipeline and raises the ntfy alert; the image is
already pushed, so the scan alerts rather than gates. Application image and
Helm-chart scanning live in the repos that build those artifacts
(`example-org/helm-charts`, `example-org/proxmox-infra`).

## Security Best Practices

### Secret Hygiene

✅ **DO**:

- Keep every value in Vault (`kv/k8s/<namespace>/<secret>`); Git holds only
  the `ExternalSecret` that references it
- Write values from stdin (`vault kv put ... key=-`), never as command-line
  arguments
- Generate long random values (for example `openssl rand -base64 32`)
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
- Use strong, randomly generated client and session secrets
- Use HTTPS for all endpoints
- Rotate the OIDC client secrets in `authentik-oidc-clients` periodically
  (Authentik and the consumers read the same Vault entry; Semaphore's copy in
  `kv/proxmox-infra/semaphore` changes with it)

❌ **DON'T**:

- Expose apps without authentication
- Use HTTP (always HTTPS via Traefik)
- Reuse the same OIDC client secret across unrelated apps
- Commit plaintext OIDC client/cookie secrets — they belong in Vault

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
- Give every app a `lan` route; put a host on `public` only when it is
  published through the tunnel, and gate it there
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
- proxmox-infra `docs/VAULT.md` - Vault runbook: unseal, KV layout,
  policies, backups
- [Authentik blueprints](../apps/infra/authentik/blueprints/) -
  Declarative providers, applications, group bindings, and the outpost
- [Authentik ForwardAuth middleware](../apps/infra/authentik/middleware.yaml) -
  Traefik ForwardAuth wiring (`authentik-forwardauth`)
