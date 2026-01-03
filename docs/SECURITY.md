# Security Guide

## Table of Contents

- [Overview](#overview)
- [Secret Management](#secret-management)
- [RBAC Configuration](#rbac-configuration)
- [Certificate Management](#certificate-management)
- [Network Security](#network-security)
- [Access Control](#access-control)
- [Security Best Practices](#security-best-practices)
- [Secret Rotation](#secret-rotation)
- [Vulnerability Management](#vulnerability-management)
- [Security Incident Response](#security-incident-response)
- [Compliance Considerations](#compliance-considerations)
- [Related Documentation](#related-documentation)

---

## Overview

This guide covers security practices and procedures for the GitOps-managed
Kubernetes homelab. Security is implemented at multiple layers: secrets
management, access control, network policies, and certificate management.

### Security Principles

1. **Defense in Depth**: Multiple security layers
2. **Principle of Least Privilege**: Minimal required permissions
3. **GitOps Security**: Secrets stored encrypted in Git
4. **Automated Security**: Automatic certificate renewal and secret rotation
5. **Audit Trail**: All changes tracked in Git

### Security Layers

```text
┌─────────────────────────────────────┐
│   Network Security (Firewall)       │
├─────────────────────────────────────┤
│   Ingress Security (TLS/HTTPS)      │
├─────────────────────────────────────┤
│   Application Security (RBAC)       │
├─────────────────────────────────────┤
│   Secret Management (Sealed Secrets)│
├─────────────────────────────────────┤
│   Storage Security (Encryption)     │
└─────────────────────────────────────┘
```

---

## Secret Management

### Sealed Secrets Overview

**Sealed Secrets** enable Git-safe storage of encrypted secrets. Secrets are
encrypted using a public key and can only be decrypted by the Sealed Secrets
Controller in the cluster.

**Key Benefits**:

- **Git-Safe**: Encrypted secrets can be committed to Git
- **GitOps-Friendly**: Secrets managed like other resources
- **Automatic**: Controller automatically unseals secrets
- **Secure**: Only controller can decrypt (RBAC-controlled)

### Sealed Secrets Workflow

```text
1. Generate Secret → 2. Seal with kubeseal → 3. Commit to Git → 4. Controller Unseals → 5. Application Uses Secret
```

### Generating Sealed Secrets

**Primary Script**: `scripts/kryptos/`

```bash
# Navigate to kryptos directory
cd scripts/kryptos

# Run the interactive tool
./kryptos

# Select app from menu and follow prompts
# Kryptos will generate sealed secrets in the app's secrets/ directory
```

### Secret Configuration

Each application has a YAML configuration file at
`scripts/kryptos/configs/<app>.yaml`:

```text
# Example: scripts/kryptos/configs/my-app.yaml
apiVersion: kryptos.dev/v1
kind: SecretConfig

metadata:
  name: my-app
  displayName: "My App"
  namespace: my-app

spec:
  secrets:
    - name: my-app-admin-secret
      displayName: "Admin Secret"
      description: "Administrator credentials"
      type: Opaque
      fields:
        - name: username
          prompt: "Admin Username"
          default: "admin"
          required: true
        - name: password
          prompt: "Admin Password"
          generator: strong
          required: true

    - name: my-app-db-secret
      displayName: "Database Secret"
      description: "Database connection information"
      type: Opaque
      fields:
        - name: host
          prompt: "DB Host"
          required: true
        - name: port
          prompt: "DB Port"
          default: "5432"
          required: true
        - name: username
          prompt: "DB Username"
          required: true
        - name: password
          prompt: "DB Password"
          generator: secure
          required: true
        - name: database
          prompt: "Database Name"
          required: true
```

### Password Generation Options

Kryptos supports multiple password generation methods via the `generator`
field:

1. **Manual Entry**: Omit `generator` field to manually enter password with
   confirmation
2. **`secure`**: 32 characters, alphanumeric (no symbols)
3. **`strong`**: 32 characters with symbols (!@#$%^&\*)
4. **`passphrase`**: 4 memorable words with number
5. **`apikey`**: 64 characters alphanumeric for APIs/tokens
6. **Auto-generation keywords**: Use `@secure`, `@strong`, `@passphrase`, or
   `@apikey` in default field

### Secret Storage

**Location**: `apps/<app-name>/secrets/`

**Naming Convention**: `<app-name>-<type>-secret.yaml`

**Example**:

```text
apps/postgresql/secrets/
├── postgresql-secret.yaml
├── gitlab-db-secret.yaml
└── kustomization.yaml
```

### Verifying Sealed Secrets

```bash
# Check SealedSecret exists
kubectl get sealedsecrets -n <namespace>

# Check if secret was unsealed
kubectl get secrets -n <namespace>

# Describe SealedSecret
kubectl describe sealedsecret <name> -n <namespace>

# Check sealed-secrets controller
kubectl get pods -n kube-system | grep sealed-secrets
kubectl logs -n kube-system -l name=sealed-secrets-controller --tail=50
```

### Security Best Practices for Secrets

1. **Never Commit Plaintext Secrets**:
   - All secrets must be SealedSecrets
   - Never commit unencrypted secrets to Git
   - Use `.gitignore` if needed (though SealedSecrets are safe)

2. **Use Strong Passwords**:
   - Use script's password generation options
   - Prefer "Strong Password" or "API Key" for sensitive secrets
   - Avoid predictable patterns

3. **Namespace Isolation**:
   - Secrets are namespace-scoped
   - Each application has its own namespace
   - Secrets cannot be accessed across namespaces

4. **Regular Rotation**:
   - Rotate secrets periodically (see [Secret Rotation](#secret-rotation))
   - Rotate after security incidents
   - Document rotation procedures

5. **Access Control**:
   - Limit who can generate secrets
   - Use RBAC to restrict secret access
   - Audit secret access (if audit logging enabled)

---

## RBAC Configuration

### Kubernetes RBAC

**Service Accounts**: Each application should use a dedicated service account

**Example**:

```text
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  namespace: my-app
```

**RoleBindings**: Grant minimal required permissions

**Example**:

```text
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: my-app-role
  namespace: my-app
rules:
  - apiGroups: [""]
    resources: ["secrets", "configmaps"]
    verbs: ["get", "list"]
```

### Best Practices

1. **Use Service Accounts**: Never use default service account
2. **Minimal Permissions**: Grant only required permissions
3. **Namespace Scoping**: Use Roles (not ClusterRoles) when possible
4. **Regular Review**: Review RBAC configurations periodically
5. **Documentation**: Document why permissions are needed

---

## Certificate Management

### Cert-Manager Overview

**Cert-Manager** automatically manages SSL/TLS certificates using Let's Encrypt.

**Key Features**:

- **Automatic Issuance**: Certificates issued automatically
- **Automatic Renewal**: Certificates renewed before expiration
- **DNS01 Challenge**: Uses Cloudflare DNS for validation
- **Production & Staging**: Separate issuers for testing

### Certificate Issuers

**Production Issuer**:
`infrastructure/cert-manager/issuers/letsencrypt-prod.yaml`

```text
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - dns01:
          cloudflare:
            apiTokenSecretRef:
              name: cloudflare-api-secret
              key: api-token
```

**Staging Issuer**: For testing (avoids rate limits)

### Certificate Configuration

**In IngressRoute**:

```text
spec:
  tls:
    certResolver: letsencrypt-prod
```

### Cloudflare API Secret

**Location**: `infrastructure/cert-manager/secrets/cloudflare-api-secret.yaml`

**Required Permissions**:

- Zone:Read
- DNS:Edit

**Security**:

- Store as SealedSecret
- Rotate API token periodically
- Use least privilege token

### Certificate Monitoring

```bash
# Check certificates
kubectl get certificates -A

# Check certificate expiration
kubectl get certificates -A -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.namespace}{"\t"}{.status.notAfter}{"\n"}{end}'

# Check certificate requests
kubectl get certificaterequests -A

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager --tail=100
```

### Certificate Best Practices

1. **Use Production Issuer**: Use `letsencrypt-prod` for production
2. **Monitor Expiration**: Set up alerts for certificate expiration
3. **Test with Staging**: Test certificate changes with staging issuer
4. **Rotate API Tokens**: Rotate Cloudflare API token periodically
5. **Backup Certificates**: Backup certificate private keys (if needed)

---

## Network Security

### Ingress Security

**Traefik** provides ingress with SSL/TLS termination.

**Security Features**:

- **HTTPS Only**: Use `websecure` entry point
- **TLS Termination**: SSL/TLS handled at ingress
- **Automatic Certificates**: Cert-Manager provides certificates
- **Wildcard Certificates**: `*.example.com` wildcard cert

### IngressRoute Configuration

```text
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: my-app-ingressroute
  namespace: my-app
spec:
  entryPoints:
    - websecure # HTTPS only
  routes:
    - kind: Rule
      match: Host(`my-app.example.com`)
      services:
        - name: my-app
          port: 80
  tls:
    certResolver: letsencrypt-prod
```

### Network Policies (Optional)

Kubernetes Network Policies can restrict pod-to-pod communication.

**Example**:

```text
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: my-app-network-policy
  namespace: my-app
spec:
  podSelector:
    matchLabels:
      app: my-app
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: traefik
      ports:
        - protocol: TCP
          port: 80
```

### External Firewall

**Network-Level Security**:

- Firewall rules at network level
- Restrict external access
- Allow only necessary ports

**Recommended Ports**:

- **80/443**: HTTP/HTTPS (Traefik)
- **22**: SSH (if needed)
- **Other**: As required by applications

### Network Security Best Practices

1. **HTTPS Everywhere**: Use HTTPS for all external access
2. **Network Policies**: Implement network policies for sensitive apps
3. **Firewall Rules**: Configure firewall at network level
4. **Minimal Exposure**: Expose only necessary services
5. **Regular Review**: Review ingress rules periodically

---

## Access Control

### ArgoCD Access

**UI Access**: <https://argo.example.com>

**Authentication**:

- Admin credentials stored as SealedSecret
- Session management
- Single admin user (homelab environment)

**Best Practices**:

- Use strong admin passwords
- Rotate admin password periodically
- Limit admin access to trusted users
- Consider SSO for multi-user environments

### Kubernetes API Access

**kubectl Access**:

- Use kubeconfig files
- Rotate credentials periodically
- Use service accounts for applications

**Best Practices**:

- Limit who has cluster admin access
- Use RBAC for all access
- Audit access logs
- Rotate credentials regularly

### Git Repository Access

**Repository**: `https://gitlab.example.com/homelab/argo-apps.git`

**Access Control**:

- GitLab access controls
- Branch protection (if configured)
- Code review requirements

**Best Practices**:

- Use strong Git credentials
- Enable 2FA for Git access
- Review commits before merging
- Protect main branch

---

## Security Best Practices

### General Practices

1. **Keep Software Updated**:
   - Update Kubernetes regularly
   - Update ArgoCD regularly
   - Update application images regularly
   - Use Renovate for automated updates

2. **Use Strong Credentials**:
   - Generate strong passwords
   - Use unique passwords per service
   - Rotate passwords regularly

3. **Enable Audit Logging**:
   - Enable Kubernetes audit logging
   - Enable ArgoCD audit logging
   - Review logs regularly

4. **Monitor Security**:
   - Monitor certificate expiration
   - Monitor secret access
   - Monitor application health
   - Set up alerts

5. **Regular Backups**:
   - Backup Git repository
   - Backup SealedSecrets
   - Backup certificates (if needed)
   - Test restore procedures

### Application Security

1. **Image Security**:
   - Use trusted image sources
   - Pin image tags (avoid `latest`)
   - Scan images for vulnerabilities
   - Use minimal base images

2. **Resource Limits**:
   - Set resource requests and limits
   - Prevent resource exhaustion
   - Monitor resource usage

3. **Network Security**:
   - Use HTTPS for all external access
   - Implement network policies
   - Restrict pod-to-pod communication

4. **Secret Management**:
   - Never commit plaintext secrets
   - Use SealedSecrets
   - Rotate secrets regularly
   - Limit secret access

### Platform Security

1. **ArgoCD Security**:
   - Use strong admin passwords
   - Rotate admin credentials periodically
   - Limit auto-sync (manual sync for safety)
   - Monitor application sync status

2. **Certificate Security**:
   - Use Let's Encrypt certificates
   - Monitor certificate expiration
   - Rotate API tokens regularly

3. **Storage Security**:
   - Encrypt volumes at rest (if supported)
   - Backup storage regularly
   - Monitor storage health

---

## Secret Rotation

### When to Rotate Secrets

- **Periodically**: Every 90 days (recommended)
- **After Security Incidents**: Immediately after suspected compromise
- **When Personnel Changes**: When team members leave
- **After Exposure**: If secrets are exposed

### Rotation Procedures

#### Application Secrets

1. **Generate New Secrets**:

   ```bash
   cd scripts/kryptos && ./kryptos
   # Select app and generate new secrets
   ```

2. **Update Application**:
   - Update secret references in manifests
   - Commit new SealedSecrets to Git

3. **Sync Application**:

   ```bash
   argocd app sync <app-name>
   ```

4. **Verify**:

   ```bash
   kubectl get secrets -n <namespace>
   ```

5. **Restart Application** (if needed):

   ```bash
   kubectl rollout restart deployment <app-name> -n <namespace>
   ```

#### Cloudflare API Token

1. **Generate New Token** in Cloudflare
2. **Create New SealedSecret**:

   ```bash
   # Update secret in infrastructure/cert-manager/secrets/
   cd scripts/kryptos && ./kryptos
   # Select cert-manager
   ```

3. **Update Cert-Manager**:

   ```bash
   argocd app sync cert-manager
   ```

4. **Verify Certificates**:

   ```bash
   kubectl get certificates -A
   ```

#### ArgoCD Admin Password

1. **Generate New Password**
2. **Update ArgoCD Secret**:

   ```bash
   # Update in infrastructure/argocd/secrets/
   cd scripts/kryptos && ./kryptos
   ```

3. **Sync ArgoCD**:

   ```bash
   argocd app sync argocd
   ```

4. **Verify Login**:

   ```bash
   argocd login argo.example.com
   ```

### Rotation Schedule

**Recommended Schedule**:

- **Application Secrets**: Every 90 days
- **API Tokens**: Every 180 days
- **Admin Passwords**: Every 90 days
- **Certificates**: Automatic (Cert-Manager)

---

## Vulnerability Management

### Image Scanning

**Best Practices**:

- Scan container images for vulnerabilities
- Use trusted image sources
- Keep images updated
- Use minimal base images

### Dependency Management

**Renovate**: Automated dependency updates

**Configuration**: `.github/renovate.json` or `.renovate.json`

**Benefits**:

- Automatic security updates
- Dependency version tracking
- Pull request creation for updates

### Security Updates

**Kubernetes**:

- Monitor Kubernetes security advisories
- Update cluster regularly
- Test updates in staging

**ArgoCD**:

- Monitor ArgoCD releases
- Update ArgoCD regularly
- Review changelogs for security fixes

**Applications**:

- Monitor application security advisories
- Update Helm charts regularly
- Update container images regularly

### Vulnerability Response

1. **Identify**: Identify vulnerable component
2. **Assess**: Assess risk and impact
3. **Mitigate**: Apply patches or workarounds
4. **Update**: Update to secure version
5. **Verify**: Verify fix is applied
6. **Document**: Document response

---

## Security Incident Response

### Incident Response Plan

1. **Identify**: Identify security incident
2. **Contain**: Contain the incident
3. **Eradicate**: Remove threat
4. **Recover**: Restore services
5. **Lessons Learned**: Document and improve

### Common Incidents

#### Compromised Secret

1. **Immediately Rotate Secret**:

   ```bash
   cd scripts/kryptos && ./kryptos
   # Select app and regenerate secrets
   ```

2. **Update Application**:

   ```bash
   git commit -am "Security: Rotate <app-name> secrets"
   git push origin main
   argocd app sync <app-name>
   ```

3. **Review Access Logs**

4. **Document Incident**

#### Certificate Compromise

1. **Revoke Certificate** (if possible)
2. **Regenerate Certificate**:

   ```bash
   kubectl delete certificate <cert-name> -n <namespace>
   # Cert-Manager will regenerate
   ```

3. **Verify New Certificate**:

   ```bash
   kubectl get certificates -n <namespace>
   ```

#### Unauthorized Access

1. **Revoke Access Immediately**
2. **Change Credentials**
3. **Review Audit Logs**
4. **Assess Impact**
5. **Document Incident**

### Incident Documentation

**Document**:

- Incident description
- Timeline
- Impact assessment
- Response actions
- Lessons learned
- Prevention measures

---

## Compliance Considerations

### GitOps Compliance

**Benefits**:

- **Audit Trail**: All changes in Git
- **Version Control**: Complete history
- **Review Process**: Code review for changes
- **Rollback**: Easy rollback capability

### Data Protection

**Secrets**:

- Encrypted in Git (SealedSecrets)
- Encrypted at rest (Kubernetes secrets)
- Encrypted in transit (TLS)

**Backups**:

- Regular backups
- Encrypted backups
- Tested restore procedures

### Compliance Access Control

**RBAC**:

- Role-based access control
- Principle of least privilege
- Regular access reviews

**Audit Logging**:

- Kubernetes audit logs
- ArgoCD audit logs
- Git commit history

### Documentation

**Security Documentation**:

- Security procedures documented
- Incident response plan
- Access control policies
- Compliance requirements

---

## Related Documentation

- [Architecture Documentation](./ARCHITECTURE.md) - System architecture
- [Application Development Guide](./APPLICATION_DEVELOPMENT.md) - Adding
  applications
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues
- [Quick Reference](./QUICK_REFERENCE.md) - Quick commands
- [Main README](../README.md) - Repository overview

---

## See Also

- [Sealed Secrets Documentation](https://github.com/bitnami-labs/sealed-secrets)
- [Cert-Manager Security](https://cert-manager.io/docs/security/)
- [Kubernetes Security](https://kubernetes.io/docs/concepts/security/)
- [ArgoCD
  Security](https://argo-cd.readthedocs.io/en/stable/operator-manual/security/)
