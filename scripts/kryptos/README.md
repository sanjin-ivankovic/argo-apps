# Kryptos 🔐

Kryptos is an enterprise-grade CLI tool for managing Kubernetes SealedSecrets.
It replaces the legacy `seal-secrets.sh` script with a robust, interactive Go
application.

## 🚀 Usage

### Running the tool

```bash
./kryptos
```

This will launch the interactive TUI (Text User Interface) where you can
select an application and generate secrets.

### Auto-Generation

When prompted for a value, you can use these magic keywords:

- `secure`: Generates a 32-char secure password.
- `strong`: Generates a 32-char password with symbols.
- `apikey`: Generates a 64-char hex API key.
- `passphrase`: Generates a random 4-word passphrase.

## ➕ Adding a New App

To add a new application, create a new YAML configuration file in the
`configs/` directory.

**File Naming:** `configs/<app_name>.yaml` (e.g., `configs/grafana.yaml`)

**Template:**

```text
apiVersion: kryptos.dev/v1
kind: SecretConfig

metadata:
  name: "grafana"
  displayName: "Grafana"
  namespace: "monitoring"

spec:
  secrets:
    - name: grafana-admin-secret
      displayName: "Grafana Admin Credentials"
      description: "Initial admin credentials for Grafana"
      type: Opaque
      fields:
        - name: admin-user
          prompt: "Admin Username"
          default: "admin"
          required: true

        - name: admin-password
          prompt: "Admin Password"
          generator: strong
          required: true

    - name: grafana-datasources
      displayName: "Datasource Credentials"
      description: "Password for the primary datasource"
      type: Opaque
      fields:
        - name: password
          prompt: "Datasource Password"
          generator: secure
          required: true
```

**Field Properties:**

- `name`: Field name in the Kubernetes secret
- `prompt`: User-facing prompt text
- `default`: Default value (optional, can use `@secure`, `@strong`,
  `@apikey`, `@passphrase` for auto-generation)
- `generator`: Auto-generate password (`secure`, `strong`, `passphrase`,
  `apikey`)
- `required`: Whether field is required (default: true)

Once saved, **restart Kryptos** and the new app will appear in the menu.

For a comprehensive template with examples, see:
`../../templates/kryptos-config.yaml`

## 🛠️ Building

Requirements: Go 1.21+

```bash
cd scripts/kryptos
go build -o kryptos main.go
```
