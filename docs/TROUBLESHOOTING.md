# Troubleshooting

This document provides solutions to common issues and operational
troubleshooting procedures.

## Table of Contents

- [General Troubleshooting](#general-troubleshooting)
- [Application Issues](#application-issues)
- [Infrastructure Issues](#infrastructure-issues)
- [Security Issues](#security-issues)
- [Common Gotchas](#common-gotchas)
- [Diagnostic Commands](#diagnostic-commands)

## General Troubleshooting

### ArgoCD Application Won't Sync

**Symptom**: Application shows `OutOfSync` but sync fails

**Diagnosis**:

```bash
# Check application status
kubectl get application <app-name> -n argocd -o yaml

# View sync errors
argocd app get <app-name>

# Check ArgoCD controller logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

**Common Causes**:

1. **Invalid YAML syntax**

   ```bash
   # Test locally first
   kubectl apply -k apps/<tier>/<app> --dry-run=server
   ```

   **Fix**: Correct YAML syntax errors in manifests

2. **Missing CRDs**

   ```bash
   # Check if IngressRoute CRD exists
   kubectl get crd ingressroutes.traefik.io
   ```

   **Fix**: Ensure Traefik deployed before apps using IngressRoute

3. **Namespace doesn't exist**

   ```bash
   # Verify namespace created
   kubectl get namespace <app-name>
   ```

   **Fix**: ApplicationSet has `CreateNamespace=true` but may fail if
   namespace has special requirements

4. **Resource quota exceeded**

   ```bash
   # Check resource usage
   kubectl describe namespace <app-name>
   ```

   **Fix**: Adjust resource limits or increase cluster capacity

---

### Application Stuck in "Progressing" State

**Symptom**: ArgoCD shows application syncing indefinitely

**Diagnosis**:

```bash
# Check pod status
kubectl get pods -n <app-name>

# Describe pod for events
kubectl describe pod <pod-name> -n <app-name>

# Check application events
kubectl get events -n <app-name> --sort-by='.lastTimestamp'
```

**Common Causes**:

1. **Image pull failure**

   ```text
   Failed to pull image: unauthorized
   ```

   **Fix**: Check image name, registry credentials, or pull policy

2. **Insufficient resources**

   ```text
   FailedScheduling: Insufficient cpu/memory
   ```

   **Fix**: Reduce resource requests or add cluster capacity

3. **PVC pending**

   ```bash
   # Check PVC status
   kubectl get pvc -n <app-name>
   ```

   **Fix**: Ensure Longhorn deployed and healthy

4. **Readiness probe failing**

   ```bash
   # Check pod logs
   kubectl logs <pod-name> -n <app-name>
   ```

   **Fix**: App not starting correctly or probe misconfigured

---

### Kustomize Build Failures

**Symptom**: ArgoCD shows "kustomize build failed"

**Diagnosis**:

```bash
# Test kustomize build locally
kubectl kustomize apps/<tier>/<app>

# Check for Helm chart issues
helm template test apps/<tier>/<app> --debug
```

**Common Causes**:

1. **Invalid kustomization.yaml**

   **Fix**: Validate YAML syntax, check resource paths

2. **Helm chart version doesn't exist**

   **Fix**: Verify chart version exists in OCI registry:

   ```bash
   helm show chart oci://registry.example.com/example-org/helm-charts/<chart> \
     --version <version>
   ```

3. **Missing values.yaml file**

   **Fix**: Ensure `valuesFile` in kustomization.yaml exists

---

## Application Issues

### Ingress Not Working (404 or Connection Refused)

**Symptom**: Accessing `https://<app>.example.com` returns 404 or connection
refused

**Diagnosis**:

```bash
# Check IngressRoute exists
kubectl get ingressroute -n <app-name>

# Describe IngressRoute for errors
kubectl describe ingressroute <app>-ingressroute -n <app-name>

# Check Traefik logs
kubectl logs -n traefik -l app.kubernetes.io/name=traefik

# Verify service exists
kubectl get svc -n <app-name>

# Test service directly
kubectl port-forward -n <app-name> svc/<app> 8080:80
curl http://localhost:8080
```

**Common Causes**:

1. **Wrong IngressRoute syntax** (not standard Ingress)

   **Fix**: Use `apiVersion: traefik.io/v1alpha1` and `kind: IngressRoute`,
   not `kind: Ingress`

2. **Service name mismatch**

   **Fix**: Ensure `services[].name` in IngressRoute matches Service
   resource name

3. **Port mismatch**

   **Fix**: Service port must match application's listening port

4. **TLS secret missing**

   **Fix**: Ensure wildcard TLS secret exists in Traefik namespace:

   ```bash
   kubectl get secret wildcard-example-com-tls -n traefik
   ```

5. **Cloudflare DNS not updated**

   **Fix**: Verify DNS points to Cloudflare Tunnel or Traefik LoadBalancer

---

### SSO Authentication Loop / Stuck Login

**Symptom**: Redirects towards `auth.example.com`, authenticates, redirects
back to the app and loops — OR the host returns 404 from the outpost, or
access is denied after a successful login.

**Diagnosis**:

```bash
# Worker logs show blueprint application; server logs show outpost decisions
kubectl -n authentik logs deploy/authentik-worker --tail=100
kubectl -n authentik logs deploy/authentik-server --tail=100

# Verify the single middleware exists
kubectl get middleware -n authentik authentik-forwardauth -o yaml

# An anonymous request to a gated host must 302 towards the authorize URL
# on auth.example.com; an unknown host via the outpost returns 404
curl -sS -o /dev/null -w '%{http_code} -> %{redirect_url}\n' \
  https://longhorn.example.com/

# OIDC token *rejection* is recorded by the apiserver, not by Authentik
kubectl -n kube-system logs kube-apiserver-talos-cp-1 | grep -i oidc
```

**Common Causes**:

1. **The IngressRoute is missing one of its two routes**

   **Fix**: A gated host needs BOTH the `authentik-forwardauth` middleware
   on the app route AND a second route matching
   ``Host(`<host>`) && PathPrefix(`/outpost.goauthentik.io/`)`` to
   `authentik-server` (namespace `authentik`, port 80, **no** middleware).
   Without the outpost route the login redirect/callback endpoints 404 and
   the flow loops.

2. **No application/provider for the host** (outpost returns 404)

   **Fix**: The blueprint side must exist: a proxy provider + application in
   `apps/infra/authentik/blueprints/10-proxy-providers.yaml` for the exact
   `external_host`, and the provider listed on the embedded outpost in
   `blueprints/30-outpost.yaml`. Confirm in Admin UI → Applications and
   Admin UI → Outposts. A failed blueprint shows "error" on its instance
   (Admin UI → Customization → Blueprints); transient errors on a first
   parallel apply clear on re-apply.

3. **User not in the `admins` group** (access denied after login)

   **Fix**: Every application carries an admins-only policy binding — add
   the user to `admins` in the Admin UI, or accept the denial as intended.

4. **Middleware reference missing the namespace**

   **Fix**: The middleware lives in the `authentik` namespace; app
   IngressRoutes must set `namespace: authentik` on the reference. The
   cross-namespace lookup works because Traefik runs with
   `providers.kubernetesCRD.allowCrossNamespace: true`.

5. **Headlamp OIDC rejected by the apiserver** (bounced back to login)

   **Fix**: The apiserver trusts only the per-application issuer
   `https://auth.example.com/application/o/headlamp/` (trailing slash) with
   audience `headlamp`. Token rejection is in the apiserver logs — see the
   diagnosis commands above. Changing the Talos
   `AuthenticationConfiguration` (in `machine.files`) cannot apply in
   immediate mode: stage it (`talosctl edit machineconfig --mode staged`)
   and reboot control planes one at a time; never run a blind full
   `make apply-configs` (the repo's `kubernetes_version` can lag the live
   cluster — always `--dry-run` first).

6. **Stale session after a config change**

   **Fix**: Always retest in a **fresh private window**; a cached Authentik
   session can mask a broken gate.

---

### Database Connection Failures

**Symptom**: Application logs show "can't connect to database" or
"connection refused"

**Diagnosis**:

```bash
# Check PostgreSQL is running
kubectl get pods -n postgresql

# Check PostgreSQL logs
kubectl logs -n postgresql -l app.kubernetes.io/name=postgresql

# Test connection from another pod
kubectl run -it --rm debug --image=postgres:18 --restart=Never -- \
  psql -h postgresql.postgresql.svc.cluster.local -U postgres
```

**Common Causes**:

1. **Database doesn't exist**

   **Fix**: Run database creation job:

   ```bash
   kubectl get job <app>-db-init -n postgresql
   kubectl logs job/<app>-db-init -n postgresql
   ```

2. **Wrong connection string**

   **Fix**: Should be `postgresql.postgresql.svc.cluster.local:5432`

3. **Credentials mismatch**

   **Fix**: Verify secret exists and matches PostgreSQL user:

   ```bash
   kubectl get secret <app>-db-secret -n <app-name>
   ```

4. **PostgreSQL not ready**

   **Fix**: Wait for PostgreSQL to be fully ready (can take 30-60s on
   first start)

---

## Infrastructure Issues

### cert-manager Certificate Not Issuing

**Symptom**: Certificate stuck in "Pending" or "False" ready state

**Diagnosis**:

```bash
# Check certificate status
kubectl get certificate -n traefik

# Describe certificate for events
kubectl describe certificate wildcard-example-com -n traefik

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager

# Check challenge status
kubectl get challenges -A
kubectl describe challenge <challenge-name> -n traefik
```

**Common Causes**:

1. **Cloudflare API token invalid**

   **Fix**: Regenerate Cloudflare API token with DNS:Edit permission,
   update SealedSecret

2. **DNS01 challenge failing**

   ```bash
   # Verify TXT record created
   dig _acme-challenge.example.com TXT
   ```

   **Fix**: Check Cloudflare API token permissions, verify DNS
   propagation

3. **Let's Encrypt rate limit hit**

   **Fix**: Use `letsencrypt-staging` for testing, wait for rate limit
   reset (weekly)

4. **Webhook not functioning**

   ```bash
   # Check webhook
   kubectl get validatingwebhookconfigurations
   ```

   **Fix**: Restart cert-manager webhook:

   ```bash
   kubectl rollout restart deployment cert-manager-webhook -n cert-manager
   ```

---

### Longhorn + Multipathd Issues (Ubuntu 24.04)

**Symptom**: Longhorn volumes fail to format with error "device
apparently in use"

**Root Cause**: Ubuntu 24.04's multipathd interferes with iSCSI devices

**Fix** (run on ALL worker nodes):

```bash
# Create multipath blacklist configuration
cat > /etc/multipath.conf << 'EOF'
defaults {
    user_friendly_names yes
}
blacklist {
    device {
        vendor "IET"
        product "VIRTUAL-DISK"
    }
}
EOF

# Restart multipathd service
systemctl restart multipathd

# Verify blacklist active
multipath -ll  # Should show no Longhorn devices
```

**Verification**:

```bash
# Check Longhorn volumes
kubectl get pv

# Check for volume attach errors
kubectl logs -n longhorn-system -l app=longhorn-manager | grep -i error
```

**Prevention**: Add multipath configuration to node
bootstrap/provisioning automation

---

### ArgoCD Self-Management Issues

**Symptom**: ArgoCD application managing ArgoCD itself shows `OutOfSync`

**Diagnosis**:

```bash
# Check ArgoCD application
kubectl get application argocd -n argocd -o yaml

# Compare desired vs actual state
argocd app diff argocd
```

**Common Causes**:

1. **Controller updating itself**

   **Fix**: This is expected during upgrades. Wait for reconciliation
   to complete.

2. **ConfigMap/Secret drift**

   **Fix**: Sync ArgoCD application to reset to Git state

3. **Custom modifications**

   **Fix**: Remove manual changes, rely on GitOps

**Safe Recovery**:

If ArgoCD becomes unresponsive:

```bash
# Manually re-apply ArgoCD infrastructure
kubectl apply -k apps/infra/argocd

# Restart ArgoCD components
kubectl rollout restart deployment argocd-server -n argocd
kubectl rollout restart deployment argocd-repo-server -n argocd
kubectl rollout restart statefulset argocd-application-controller -n argocd
```

---

### Traefik Not Getting External IP

**Symptom**: Traefik LoadBalancer service shows `<pending>` external IP

**Diagnosis**:

```bash
# Check Traefik service
kubectl get svc -n traefik

# Check MetalLB logs
kubectl logs -n metallb-system -l app.kubernetes.io/component=controller

# Verify IP pool configured
kubectl get ipaddresspool -n metallb-system
kubectl get l2advertisement -n metallb-system
```

**Common Causes**:

1. **MetalLB not deployed**

   **Fix**: Deploy MetalLB (sync wave 1):

   ```bash
   argocd app sync metallb
   ```

2. **IP pool exhausted**

   **Fix**: Expand IP pool range in MetalLB configuration

3. **L2Advertisement missing**

   **Fix**: Create L2Advertisement resource for IP pool

---

## Security Issues

### SealedSecret Not Unsealing

**Symptom**: SealedSecret exists but Secret not created

**Diagnosis**:

```bash
# Check SealedSecret status
kubectl get sealedsecrets -n <namespace>

# Check sealed-secrets controller logs
kubectl logs -n kube-system -l name=sealed-secrets-controller

# Verify controller running
kubectl get pods -n kube-system -l name=sealed-secrets-controller
```

**Common Causes**:

1. **Controller not running**

   **Fix**: Deploy sealed-secrets controller:

   ```bash
   argocd app sync sealed-secrets
   ```

2. **Encryption/decryption key mismatch**

   **Fix**: If you restored from backup, ensure the sealed-secrets
   private key is restored:

   ```bash
   kubectl apply -f sealed-secrets-key-backup.yaml
   kubectl delete pod -n kube-system -l name=sealed-secrets-controller
   ```

3. **Invalid SealedSecret format**

   **Fix**: Regenerate secret with Kryptos or kubeseal

4. **Namespace mismatch**

   **Fix**: SealedSecret namespace must match target Secret namespace
   (strict scoping)

---

### Shared PostgreSQL Database / Credentials Drift

**Symptom**: An app that uses the shared PostgreSQL cluster (Harbor,
DocuSeal, LiteLLM, Joplin, Memos, SnapOtter, Authentik) retries connections
with `connection refused`, `authentication failed`, or `database "<app>"
does not exist`.

**Diagnosis**:

```bash
# Verify PostgreSQL is running and not OOMKilled
kubectl get pods -n postgresql
kubectl describe deploy -n postgresql postgresql | grep -A 5 "Last State"

# Check that the app's DB/user exist (replace <app>)
PGPW=$(kubectl -n postgresql get secret postgresql-secret \
  -o jsonpath='{.data.postgres-password}' | base64 -d)
kubectl exec -n postgresql deploy/postgresql -- env PGPASSWORD="$PGPW" \
  psql -U postgres -c "\l" -c "\du" | grep <app>
```

**Fix**:

1. Ensure PostgreSQL is running and has enough memory
   (`apps/data/postgresql/values.yaml` sets requests/limits explicitly).

2. Run the database creation job if the app's DB or user is missing (jobs
   live in `apps/data/postgresql/jobs/`, e.g. `authentik`):

   ```bash
   kubectl apply -f apps/data/postgresql/jobs/authentik-db-create-job.yaml
   kubectl wait --for=condition=complete -n postgresql \
     job/create-authentik-database --timeout=120s
   ```

3. If the password the app uses drifts from the one stored in PostgreSQL,
   regenerate both secrets via Kryptos using the **same** password value, then
   re-run the relevant database job.

---

## Common Gotchas

### 1. Auto-Sync is Disabled Everywhere

**Gotcha**: After pushing to Git, applications don't automatically sync

**Why**: Intentional design for deliberate change management

**Solution**: Manually sync in ArgoCD UI after every change

```bash
# Via CLI
argocd app sync <app-name>

# Via UI
https://argo.example.com → Select app → Sync button
```

---

### 2. Use IngressRoute, NOT Standard Ingress

**Gotcha**: Creating `kind: Ingress` doesn't work

**Why**: Traefik uses custom IngressRoute CRD

**Solution**: Always use Traefik's IngressRoute:

```text
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: myapp-ingressroute
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`myapp.example.com`)
      kind: Rule
      services:
        - name: myapp
          port: 80
```

---

### 3. Namespace = Application Name (Usually)

**Gotcha**: Assuming app can be in different namespace

**Why**: The Application name is `{{.path.basename}}`; the namespace defaults
to it but is set via `config.yaml`

**Exceptions** (namespace differs from the directory basename):

- sealed-secrets → `kube-system`
- metallb → `metallb-system`
- longhorn → `longhorn-system`
- external-services → `traefik`

**Solution**: Match directory name, namespace, and application name unless an
override is required (set `namespace:` in `config.yaml`)

---

### 4. Longhorn is Default StorageClass

**Gotcha**: PVCs created without specifying StorageClass fail

**Why**: May expect different default

**Solution**: Don't specify `storageClassName` (defaults to Longhorn),
or explicitly set to `longhorn`

---

### 5. Sealed Secrets Are Namespace-Scoped

**Gotcha**: Moving app to different namespace breaks secret

**Why**: SealedSecret namespace encoded in encryption

**Solution**: Regenerate SealedSecret with Kryptos for new namespace

---

### 6. Priority Classes Must Exist Before Pods

**Gotcha**: Pods fail to schedule if priority class doesn't exist

**Why**: Priority classes are cluster-wide resources

**Solution**: Priority classes deployed in sync wave -1 (before everything else)

---

### 7. cert-manager DNS01 Challenge Requires Cloudflare API Token

**Gotcha**: Let's Encrypt certificate issuance fails silently

**Why**: cert-manager can't create DNS TXT records

**Solution**: Ensure Cloudflare API token SealedSecret exists with
`Zone:DNS:Edit` permission

---

### 8. PostgreSQL Takes Time to Initialize

**Gotcha**: Applications crash-loop on first deployment

**Why**: PostgreSQL init can take 30-60 seconds

**Solution**: Use `initContainers` to wait for database:

```text
initContainers:
  - name: wait-for-db
    image: busybox
    command:
      [
        "sh",
        "-c",
        "until nc -z postgresql.postgresql.svc.cluster.local 5432; do sleep 1; done",
      ]
```

---

### 9. External Services Need ServersTransport for Self-Signed Certs

**Gotcha**: Proxied external service returns 500 error

**Why**: Traefik validates TLS certificate by default

**Solution**: Create ServersTransport with `insecureSkipVerify: true`:

```text
apiVersion: traefik.io/v1alpha1
kind: ServersTransport
metadata:
  name: myservice-st
spec:
  insecureSkipVerify: true
```

---

### 10. Kryptos Requires Sealed Secrets Controller Running

**Gotcha**: Kryptos fails with "can't fetch certificate"

**Why**: Kryptos calls `kubeseal --fetch-cert` under the hood

**Solution**: Ensure sealed-secrets controller deployed and healthy:

```bash
kubectl get pods -n kube-system -l name=sealed-secrets-controller
kubeseal --fetch-cert  # Should return public key
```

---

## Diagnostic Commands

### Check Cluster Health

```bash
# Node status
kubectl get nodes

# System pods
kubectl get pods -n kube-system

# Resource usage
kubectl top nodes
kubectl top pods -A

# Events (recent issues)
kubectl get events -A --sort-by='.lastTimestamp' | tail -20
```

---

### Check Application Status

```bash
# All applications
kubectl get applications -n argocd

# Specific app details
argocd app get <app-name>

# Application logs
kubectl logs -n <app-name> -l app=<app-name>

# Application events
kubectl get events -n <app-name> --sort-by='.lastTimestamp'
```

---

### Check Storage

```bash
# PersistentVolumeClaims
kubectl get pvc -A

# PersistentVolumes
kubectl get pv

# Longhorn volumes
kubectl get volumes -n longhorn-system

# StorageClasses
kubectl get storageclass
```

---

### Check Networking

```bash
# Services
kubectl get svc -A

# IngressRoutes
kubectl get ingressroute -A

# Traefik middleware
kubectl get middleware -A

# LoadBalancer IPs
kubectl get svc -A -o wide | grep LoadBalancer

# MetalLB IP pool
kubectl get ipaddresspool -n metallb-system
```

---

### Check Certificates

```bash
# Certificates
kubectl get certificate -A

# Certificate details
kubectl describe certificate <cert-name> -n <namespace>

# ACME challenges
kubectl get challenges -A

# cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager
```

---

### Check Secrets

```bash
# SealedSecrets
kubectl get sealedsecrets -A

# Unsealed Secrets
kubectl get secrets -A

# Sealed Secrets controller logs
kubectl logs -n kube-system -l name=sealed-secrets-controller
```

---

## Getting Help

**Before Opening an Issue**:

1. ✅ Check this troubleshooting guide
2. ✅ Search existing issues in GitLab/GitHub
3. ✅ Check ArgoCD and component logs
4. ✅ Test locally with `--dry-run=server`
5. ✅ Verify components deployed in correct sync wave order

**Include in Issue**:

- Error messages (from logs, events, ArgoCD UI)
- Kubernetes version
- Component versions (ArgoCD, Traefik, cert-manager, etc.)
- Relevant configuration (kustomization.yaml, values.yaml)
- Steps to reproduce

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and design
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md) - Infrastructure component details
- [SECURITY.md](SECURITY.md) - Security configuration
- [APPLICATIONS.md](APPLICATIONS.md) - Application catalog
- [CI-CD-PIPELINE.md](CI-CD-PIPELINE.md) - CI/CD pipeline details
- [argocd/README.md](../argocd/README.md) -
  Bootstrap procedures
