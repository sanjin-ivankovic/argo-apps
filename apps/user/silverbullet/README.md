# SilverBullet

## Purpose

SilverBullet, a Markdown notes server used as a live scratchpad: text written
on the personal machine (terminal commands, PR descriptions) shows up within
seconds in a browser on the work machine, and edits there come back. OpenGist
stays the snippet store and Obsidian the notes app.

The work network strips WebSocket upgrades. SilverBullet uses none: open
browsers get changes over Server-Sent Events on `/.events`, and poll over
plain HTTP when that stream fails.

## Deployment

- Path: `apps/user/silverbullet/`
- Namespace: `silverbullet`
- Sync wave: `"6"` (user tier, auto-sync)
- Chart: homelab `silverbullet` from
  `oci://registry.example.com/example-org/helm-charts` (helm-charts
  `charts/silverbullet/`, `-slim` image without Chromium), version pinned in
  `kustomization.yaml`
- Route: `https://silverbullet.example.com` on the `lan` and `public`
  entrypoints, no ForwardAuth (it breaks SilverBullet's background requests
  when the proxy session expires). Cloudflare Access gates the tunnel
  hostname; sign-in is Authentik OIDC (client `silverbullet`, `admins`
  group) plus one local recovery admin.
- `SB_DISABLE_SERVICE_WORKER` keeps no offline copy of the space in the
  browser; the chart default `SB_SHELL_BACKEND=off` disables shell commands.

## Dependencies

- Authentik: OIDC provider `silverbullet-oidc` in
  `apps/infra/authentik/blueprints/20-oauth2-providers.yaml`; its client
  secret is `SILVERBULLET_CLIENT_SECRET` in Vault
  `kv/k8s/authentik/authentik-oidc-clients`.
- No database and no Secret in this namespace. All state lives in
  `/data/silverbullet` on the `silverbullet-data` volume (1Gi, Longhorn):
  `users.json`, `authentication.json` (the OIDC client settings, secret
  included), `spaces.json`, `server.json` and the pages under `spaces/`.

## Operations

- **An empty data folder opens an unauthenticated setup wizard** at
  `/.setup/` where the first visitor becomes admin; on a public route only
  Cloudflare Access stands in front of it. After a volume loss, complete the
  wizard at once: primary URL `https://silverbullet.example.com`, first space
  bound to that host.
- The data folder is `SB_FOLDER=/data/silverbullet`, not the volume root:
  the root holds `lost+found`, which SilverBullet counts as content and then
  boots legacy single-space mode with no login at all.
- Accounts, spaces, API tokens and single sign-on are managed in the
  dashboard at `/.dashboard`. Keep one local admin account for recovery.
- Single sign-on: Admin, Authentication, OpenID Connect, issuer
  `https://auth.example.com/application/o/silverbullet/`, client ID
  `silverbullet`, secret from Vault. Then Users, Add user, SSO, with the
  email of the Authentik account.
- The `silverbullet-data` volume has no off-cluster copy. It holds scratch
  text only; losing it means re-running the setup wizard.
- Upgrades are chart bumps (Renovate). Upstream ships about monthly with
  frequent breaking changes; read the changelog before merging a minor bump.
