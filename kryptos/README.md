# kryptos configs

This directory holds the **homelab SealedSecret configs** — the per-app YAML
definitions kryptos reads to generate sealed secrets. The kryptos **engine**
(the CLI/TUI) lives in its own repo:

- **<https://source.example.com/example-org/kryptos>**

## Usage

Grab a released kryptos binary (pinned version) and run it from the **argo-apps
repo root** — the [`kryptos.toml`](../../kryptos.toml) there points it at these
configs and at the cluster's sealed-secret output tree.

```bash
# one-time: install a pinned release.
# example-org/kryptos is PRIVATE — the download needs a GitLab token with
# read_api scope on example-org/kryptos.
VER=v0.1.0
GITLAB_TOKEN=<your-read-PAT>
curl -fsSL -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" -o /tmp/kryptos.tgz \
  "https://source.example.com/api/v4/projects/homelab%2Fkryptos/releases/${VER}/downloads/kryptos_${VER#v}_$(uname -s | tr A-Z a-z)_$(uname -m | sed 's/x86_64/amd64/').tar.gz"
tar xzf /tmp/kryptos.tgz -C /usr/local/bin kryptos

# from the argo-apps repo root:
kryptos                      # interactive TUI
kryptos validate             # check every config (no cluster needed)
kryptos seal <app> <secret>  # non-interactive seal
kryptos audit                # config ↔ sealed-secret drift
```

## Adding / editing a config

Each app is `configs/<app>.yaml` (schema `kryptos.dev/v1`). Editors get
autocomplete + validation from the JSON schema via the
`# yaml-language-server: $schema=…` modeline — see the kryptos repo's
`templates/kryptos-config.yaml` for an annotated reference and `schema/` for the
field list.

Retired apps' configs live in [`configs/.archive/`](configs/.archive/)
(reference-only, gitignored).
