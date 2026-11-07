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
# one-time: install a release (`make install` in a kryptos checkout does the
# same and verifies the checksum). Anonymous pull from Harbor; needs oras.
VER=v0.6.0
mkdir -p /tmp/kryptos
oras pull --output /tmp/kryptos "registry.example.com/example-org/kryptos/cli:${VER}"
tar xzf "/tmp/kryptos/kryptos_${VER#v}_$(uname -s | tr A-Z a-z)_$(uname -m | sed 's/x86_64/amd64/').tar.gz" \
  -C /usr/local/bin kryptos

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

Retired apps' configs live in
[`.archive/kryptos/configs/`](../.archive/kryptos/configs/) (tracked, frozen
reference).
