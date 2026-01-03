# Troubleshooting Guide

## Table of Contents

- [Overview](#overview)
- [Diagnostic Commands](#diagnostic-commands)
- [ArgoCD Issues](#argocd-issues)
- [Application Deployment Issues](#application-deployment-issues)
- [Storage Issues](#storage-issues)
- [Network Issues](#network-issues)
- [Certificate Issues](#certificate-issues)
- [Secret Management Issues](#secret-management-issues)
- [Database Issues](#database-issues)
- [Pod Issues](#pod-issues)
- [Node Reboot Procedures](#node-reboot-procedures)
- [Emergency Procedures](#emergency-procedures)
- [Common Error Messages](#common-error-messages)
- [Related Documentation](#related-documentation)

---

## Overview

This guide provides comprehensive troubleshooting procedures for common
issues in the GitOps-managed Kubernetes homelab. Each section includes
diagnostic commands, root cause analysis, and step-by-step resolution
procedures.

### Quick Diagnostic Checklist

When troubleshooting, check in this order:

1. **Cluster Health**: Are nodes and core components running?
2. **ArgoCD Status**: Are applications syncing correctly?
3. **Application Status**: Are pods running and healthy?
4. **Network**: Are services accessible?
5. **Storage**: Are volumes mounted correctly?
6. **Secrets**: Are secrets available to applications?

### Getting Help

- **ArgoCD UI**: `https://argo.example.com` - Visual status and logs
- **Kubectl**: Command-line diagnostics
- **Logs**: Application and system logs
- **Events**: Kubernetes events for detailed error messages

---

## Diagnostic Commands

### Cluster Health

```bash
# Check node status
kubectl get nodes

# Check all pods across namespaces
kubectl get pods -A

# Check for non-running pods
kubectl get pods -A | grep -vE "(Running|Completed)"

# Check system components
kubectl get pods -n kube-system
kubectl get pods -n longhorn-system
kubectl get pods -n argocd
kubectl get pods -n traefik
```

### ArgoCD Status

```bash
# List all applications
kubectl get applications -n argocd

# Get application details
kubectl get application <app-name> -n argocd -o yaml

# Check ArgoCD controller logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller --tail=100

# Check ArgoCD repo server logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server --tail=100

# ArgoCD CLI status
argocd app list
argocd app get <app-name>
argocd app history <app-name>
```

### Application Status

```bash
# Check pods in namespace
kubectl get pods -n <namespace>

# Describe pod for details
kubectl describe pod <pod-name> -n <namespace>

# View pod logs
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous  # Previous container instance

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Check services
kubectl get svc -n <namespace>

# Check ingress
kubectl get ingressroute -n <namespace>
```

### Resource Usage

```bash
# Check resource usage
kubectl top nodes
kubectl top pods -A

# Check resource quotas
kubectl describe quota -n <namespace>

# Check persistent volumes
kubectl get pv,pvc -A
```

---

## ArgoCD Issues

### Application Not Appearing in ArgoCD

**Symptoms**:

- Application not listed in ArgoCD UI
- ApplicationSet not generating applications

**Diagnosis**:

```bash
# Check ApplicationSet
kubectl get applicationset -n argocd

# Describe ApplicationSet
kubectl describe applicationset apps-prod -n argocd

# Check generated applications
kubectl get applications -n argocd

# Check ApplicationSet controller logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-applicationset-controller --tail=100
```

**Common Causes**:

1. Application not added to ApplicationSet
2. Invalid path in ApplicationSet
3. Namespace mismatch
4. ApplicationSet controller not running

**Resolution**:

1. **Verify ApplicationSet configuration**:

   ```bash
   # Check apps-set.yaml
   cat argocd/applications/apps-set.yaml | grep -A 3 "my-app"
   ```

2. **Verify path exists**:

   ```bash
   # Check if path exists in Git
   ls -la apps/my-app/kustomization.yaml
   ```

3. **Check ApplicationSet status**:

   ```bash
   kubectl get applicationset apps-prod -n argocd -o yaml | grep -A 10 "status"
   ```

4. **Restart ApplicationSet controller** (if needed):

   ```bash
   kubectl delete pod -n argocd -l app.kubernetes.io/name=argocd-applicationset-controller
   ```

### Application Sync Failing

**Symptoms**:

- Application shows "SyncFailed" or "Unknown" status
- Error messages in ArgoCD UI

**Diagnosis**:

```bash
# Get application status
argocd app get <app-name>

# View sync operation details
argocd app get <app-name> --refresh

# Check application events
kubectl describe application <app-name> -n argocd

# View sync logs
argocd app logs <app-name> --tail=50
```

**Common Causes**:

1. Invalid Kustomization syntax
2. Helm chart not accessible
3. Missing secrets
4. Resource conflicts
5. Git repository access issues

**Resolution**:

1. **Validate Kustomization**:

   ```bash
   # Test kustomization build
   kubectl kustomize apps/<app-name>

   # Test with dry-run
   kubectl kustomize apps/<app-name> | kubectl apply --dry-run=client -f -
   ```

2. **Check Helm Chart**:

   ```bash
   # For Helm-based apps, verify chart is accessible
   helm repo list
   helm search repo <chart-name>
   ```

3. **Check Git Access**:

   ```bash
   # Verify ArgoCD can access repository
   argocd repo get https://gitlab.example.com/homelab/argo-apps.git
   ```

4. **View Detailed Error**:

   ```bash
   # Get full application spec
   kubectl get application <app-name> -n argocd -o yaml

   # Look for status.conditions
   kubectl get application <app-name> -n argocd -o jsonpath='{.status.conditions}'
   ```

5. **Manual Sync**:

   ```bash
   # Force refresh and sync
   argocd app get <app-name> --refresh
   argocd app sync <app-name>
   ```

### Application Out of Sync

**Symptoms**:

- Application shows "OutOfSync" status
- Changes not applied to cluster

**Diagnosis**:

```bash
# Check sync status
argocd app get <app-name>

# View diff
argocd app diff <app-name>

# Check what's out of sync
kubectl get application <app-name> -n argocd -o jsonpath='{.status.resources}' | jq
```

**Resolution**:

1. **Review Diff**:

   ```bash
   argocd app diff <app-name>
   ```

2. **Manual Sync**:

   ```bash
   # Sync application
   argocd app sync <app-name>

   # Or sync with specific options
   argocd app sync <app-name> --prune --force
   ```

3. **Check Sync Options**:

   ```bash
   # Verify sync options in ApplicationSet
   cat argocd/applications/apps-set.yaml | grep -A 5 "syncOptions"
   ```

### ArgoCD Repository Access Issues

**Symptoms**:

- "repository not accessible" errors
- "authentication failed" errors

**Diagnosis**:

```bash
# List repositories
argocd repo list

# Get repository details
argocd repo get https://gitlab.example.com/homelab/argo-apps.git

# Test repository access
argocd repo get https://gitlab.example.com/homelab/argo-apps.git --refresh
```

**Resolution**:

1. **Verify Repository URL**:

   ```bash
   # Check repository URL in app-of-apps
   cat argocd/app-of-apps.yaml | grep repoURL
   ```

2. **Check Credentials**:

   ```bash
   # If using credentials, verify they're correct
   argocd repo get https://gitlab.example.com/homelab/argo-apps.git
   ```

3. **Refresh Repository**:

   ```bash
   argocd repo get https://gitlab.example.com/homelab/argo-apps.git --refresh
   ```

---

## Application Deployment Issues

### Application Not Starting

**Symptoms**:

- Pods in CrashLoopBackOff
- Pods not reaching Ready state
- Application not accessible

**Diagnosis**:

```bash
# Check pod status
kubectl get pods -n <namespace>

# Describe pod
kubectl describe pod <pod-name> -n <namespace>

# View pod logs
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

**Common Causes**:

1. Configuration errors
2. Missing secrets
3. Resource limits too low
4. Image pull failures
5. Database connection issues

**Resolution**:

1. **Check Configuration**:

   ```bash
   # View deployment configuration
   kubectl get deployment <app-name> -n <namespace> -o yaml

   # Check ConfigMaps
   kubectl get configmap -n <namespace>
   kubectl describe configmap <configmap-name> -n <namespace>
   ```

2. **Check Secrets**:

   ```bash
   # Verify secrets exist
   kubectl get secrets -n <namespace>

   # Check secret is unsealed
   kubectl get sealedsecrets -n <namespace>
   kubectl get secrets -n <namespace>
   ```

3. **Check Resource Limits**:

   ```bash
   # View resource requests/limits
   kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Limits\|Requests"
   ```

4. **Check Image Pull**:

   ```bash
   # Check for image pull errors
   kubectl describe pod <pod-name> -n <namespace> | grep -i "image\|pull"
   ```

### Application Not Accessible via Ingress

**Symptoms**:

- Application not reachable via domain
- 404 or 502 errors
- Certificate errors

**Diagnosis**:

```bash
# Check IngressRoute
kubectl get ingressroute -n <namespace>

# Describe IngressRoute
kubectl describe ingressroute <ingressroute-name> -n <namespace>

# Check Traefik logs
kubectl logs -n traefik -l app.kubernetes.io/name=traefik --tail=100

# Check service
kubectl get svc -n <namespace>
kubectl describe svc <service-name> -n <namespace>

# Check endpoints
kubectl get endpoints -n <namespace>
```

**Resolution**:

1. **Verify IngressRoute Configuration**:

   ```bash
   # Check IngressRoute spec
   kubectl get ingressroute <name> -n <namespace> -o yaml

   # Verify service name matches
   kubectl get ingressroute <name> -n <namespace> -o jsonpath='{.spec.routes[*].services[*].name}'
   kubectl get svc -n <namespace>
   ```

2. **Check Service Endpoints**:

   ```bash
   # Verify service has endpoints
   kubectl get endpoints <service-name> -n <namespace>

   # If no endpoints, check pod labels match service selector
   kubectl get pods -n <namespace> --show-labels
   kubectl get svc <service-name> -n <namespace> -o jsonpath='{.spec.selector}'
   ```

3. **Check Traefik Configuration**:

   ```bash
   # View Traefik logs for routing issues
   kubectl logs -n traefik -l app.kubernetes.io/name=traefik --tail=200 | grep <app-name>
   ```

---

## Storage Issues

### Longhorn Volume Mount Failures

**Symptoms**:

- Pods stuck in "ContainerCreating"
- "already mounted" or "device in use" errors
- Volume attachment failures

**Diagnosis**:

```bash
# Check volume attachments
kubectl get volumeattachment

# Check PVC status
kubectl get pvc -n <namespace>

# Check Longhorn volumes
kubectl get volumes.longhorn.io -n longhorn-system

# Check Longhorn manager logs
kubectl logs -n longhorn-system -l app=longhorn-manager --tail=100

# Check Longhorn CSI plugin
kubectl get pods -n longhorn-system | grep csi
kubectl logs -n longhorn-system -l app=longhorn-csi-plugin --tail=100
```

**Resolution**:

1. **Check for Stale Volume Attachments**:

   ```bash
   # List all volume attachments
   kubectl get volumeattachment

   # Check for attachments on wrong nodes
   kubectl get volumeattachment -o wide
   ```

2. **Restart Longhorn CSI Plugin**:

   ```bash
   # Restart CSI plugin on affected node
   kubectl delete pod -n longhorn-system -l app=longhorn-csi-plugin --field-selector spec.nodeName=<node-name>
   ```

3. **Manually Detach Volume**:

   ```bash
   # Scale down application
   kubectl scale deployment <app> -n <namespace> --replicas=0

   # Wait for volume to detach (check Longhorn UI)
   # Then scale back up
   kubectl scale deployment <app> -n <namespace> --replicas=1
   ```

4. **Longhorn UI Check**:
   - Access Longhorn UI
   - Check volume status
   - Manually detach if needed
   - Check for replica issues

### PVC Not Binding

**Symptoms**:

- PVC stuck in "Pending"
- "no storage class" errors

**Diagnosis**:

```bash
# Check PVC status
kubectl get pvc -n <namespace>
kubectl describe pvc <pvc-name> -n <namespace>

# Check storage classes
kubectl get storageclass

# Check Longhorn storage class
kubectl get storageclass longhorn -o yaml
```

**Resolution**:

1. **Verify Storage Class**:

   ```bash
   # Check if longhorn storage class exists
   kubectl get storageclass longhorn

   # If missing, check Longhorn installation
   kubectl get pods -n longhorn-system
   ```

2. **Check PVC Configuration**:

   ```bash
   # Verify PVC specifies storage class
   kubectl get pvc <pvc-name> -n <namespace> -o yaml | grep storageClassName

   # Should be: storageClassName: longhorn
   ```

3. **Check Longhorn Health**:

   ```bash
   # Verify Longhorn is healthy
   kubectl get pods -n longhorn-system

   # Check Longhorn manager
   kubectl logs -n longhorn-system -l app=longhorn-manager --tail=50
   ```

### Multipathd Conflict (Critical)

**Symptoms**:

- New Longhorn volumes fail to format
- Error: `mke2fs: /dev/longhorn/pvc-XXX is apparently in use by the system`

**Root Cause**:
Multipathd daemon detects Longhorn iSCSI devices and claims them, preventing
formatting.

**Resolution**:

**On each worker node**, add Longhorn device blacklist:

```bash
# Create/update multipath.conf
cat > /etc/multipath.conf << 'EOF'
defaults {
    user_friendly_names yes
}

# Blacklist Longhorn iSCSI devices to prevent multipathd interference
blacklist {
    device {
        vendor "IET"
        product "VIRTUAL-DISK"
    }
}
EOF

# Restart multipathd
systemctl restart multipathd

# Verify blacklist is active
multipath -ll  # Should not show Longhorn devices
```

**Reference**: [Longhorn GitHub Issue
\#1210](https://github.com/longhorn/longhorn/issues/1210#issuecomment-671689746)

**Important**: Required for Ubuntu 24.04 with Longhorn v1.10.0+. Old
volumes work fine, but NEW volume creation fails without this fix.

---

## Network Issues

### Service Not Accessible

**Symptoms**:

- Cannot connect to service
- Connection timeouts
- DNS resolution failures

**Diagnosis**:

```bash
# Check service
kubectl get svc -n <namespace>
kubectl describe svc <service-name> -n <namespace>

# Check endpoints
kubectl get endpoints -n <namespace>
kubectl describe endpoints <service-name> -n <namespace>

# Test DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup <service-name>.<namespace>.svc.cluster.local

# Test connectivity
kubectl run -it --rm debug --image=busybox --restart=Never -- wget -O- http://<service-name>.<namespace>.svc.cluster.local:<port>
```

**Resolution**:

1. **Verify Service Endpoints**:

   ```bash
   # If no endpoints, check pod labels match service selector
   kubectl get pods -n <namespace> --show-labels
   kubectl get svc <service-name> -n <namespace> -o jsonpath='{.spec.selector}'
   ```

2. **Check Pod Labels**:

   ```bash
   # Ensure pod labels match service selector
   kubectl get pods -n <namespace> -o jsonpath='{.items[*].metadata.labels}'
   ```

### Ingress Not Routing

**Symptoms**:

- Domain not resolving
- 404 errors
- Traefik not routing to service

**Diagnosis**:

```bash
# Check IngressRoute
kubectl get ingressroute -n <namespace>
kubectl describe ingressroute <name> -n <namespace>

# Check Traefik logs
kubectl logs -n traefik -l app.kubernetes.io/name=traefik --tail=200

# Check Traefik service
kubectl get svc -n traefik
```

**Resolution**:

1. **Verify IngressRoute Configuration**:

   ```bash
   # Check IngressRoute spec
   kubectl get ingressroute <name> -n <namespace> -o yaml

   # Verify:
   # - Service name matches actual service
   # - Port matches service port
   # - Host matches DNS configuration
   ```

2. **Check DNS Configuration**:

   ```bash
   # Verify DNS points to MetalLB IP
   # Check MetalLB service
   kubectl get svc -n traefik traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

   # Verify DNS A record points to this IP
   dig <domain-name>
   ```

3. **Check Traefik Entry Points**:

   ```bash
   # Verify entry points in IngressRoute match Traefik configuration
   kubectl get ingressroute <name> -n <namespace> -o jsonpath='{.spec.entryPoints}'
   ```

---

## Certificate Issues

### Certificate Not Issuing

**Symptoms**:

- Certificate stuck in "Pending"
- Certificate order failing
- TLS errors

**Diagnosis**:

```bash
# Check certificates
kubectl get certificates -A
kubectl describe certificate <cert-name> -n <namespace>

# Check certificate requests
kubectl get certificaterequests -A
kubectl describe certificaterequest <name> -n <namespace>

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager --tail=100
kubectl logs -n cert-manager -l app=cert-manager-webhook --tail=100

# Check issuer
kubectl get issuers -n <namespace>
kubectl describe issuer <issuer-name> -n <namespace>
```

**Resolution**:

1. **Verify DNS Propagation**:

   ```bash
   # Check DNS for domain
   dig <domain-name>
   nslookup <domain-name>

   # For DNS01 challenge, verify TXT record
   dig TXT _acme-challenge.<domain-name>
   ```

2. **Check Cloudflare API Secret**:

   ```bash
   # Verify secret exists
   kubectl get secret cloudflare-api-secret -n cert-manager

   # Check secret has correct keys
   kubectl get secret cloudflare-api-secret -n cert-manager -o jsonpath='{.data}' | jq 'keys'
   ```

3. **Check Issuer Configuration**:

   ```bash
   # Verify issuer is configured correctly
   kubectl get issuer letsencrypt-prod -n <namespace> -o yaml
   ```

4. **Check Certificate Order**:

   ```bash
   # View certificate order details
   kubectl describe certificate <cert-name> -n <namespace>

   # Look for events and conditions
   kubectl get certificate <cert-name> -n <namespace> -o jsonpath='{.status.conditions}'
   ```

### Certificate Expired

**Symptoms**:

- TLS errors
- Browser shows expired certificate

**Diagnosis**:

```bash
# Check certificate expiration
kubectl get certificate -A -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.namespace}{"\t"}{.status.notAfter}{"\n"}{end}'

# Check certificate details
kubectl get certificate <cert-name> -n <namespace> -o yaml | grep -A 5 "notAfter"
```

**Resolution**:

1. **Force Certificate Renewal**:

   ```bash
   # Delete certificate (cert-manager will recreate)
   kubectl delete certificate <cert-name> -n <namespace>

   # Or delete secret to trigger renewal
   kubectl delete secret <cert-secret-name> -n <namespace>
   ```

2. **Check Cert-Manager**:

   ```bash
   # Verify cert-manager is running
   kubectl get pods -n cert-manager

   # Check logs for renewal attempts
   kubectl logs -n cert-manager -l app=cert-manager --tail=100 | grep <domain-name>
   ```

---

## Secret Management Issues

### Secret Not Unsealing

**Symptoms**:

- Application cannot find secret
- SealedSecret exists but secret not created
- Application fails with "secret not found"

**Diagnosis**:

```bash
# Check SealedSecret
kubectl get sealedsecrets -n <namespace>
kubectl describe sealedsecret <name> -n <namespace>

# Check if secret was created
kubectl get secrets -n <namespace>
kubectl describe secret <name> -n <namespace>

# Check sealed-secrets controller
kubectl get pods -n kube-system | grep sealed-secrets
kubectl logs -n kube-system -l name=sealed-secrets-controller --tail=100
```

**Resolution**:

1. **Verify Sealed Secrets Controller**:

   ```bash
   # Check controller is running
   kubectl get pods -n kube-system | grep sealed-secrets

   # Check controller logs
   kubectl logs -n kube-system -l name=sealed-secrets-controller --tail=100
   ```

2. **Check SealedSecret Status**:

   ```bash
   # View SealedSecret status
   kubectl get sealedsecret <name> -n <namespace> -o yaml | grep -A 10 "status"

   # Check for errors
   kubectl describe sealedsecret <name> -n <namespace>
   ```

3. **Verify Namespace**:

   ```bash
   # Ensure SealedSecret namespace matches target namespace
   kubectl get sealedsecret <name> -n <namespace> -o jsonpath='{.metadata.namespace}'
   ```

4. **Regenerate SealedSecret** (if needed):

   ```bash
   # Re-run seal script
   ./scripts/seal-secrets.sh <app-name>
   ```

### Secret Wrong Namespace

**Symptoms**:

- Secret exists in wrong namespace
- Application cannot find secret

**Resolution**:

1. **Check Secret Namespace**:

   ```bash
   # List secrets in namespace
   kubectl get secrets -n <namespace>

   # Check if secret exists in different namespace
   kubectl get secrets -A | grep <secret-name>
   ```

2. **Copy Secret** (if needed):

   ```bash
   # Get secret from source namespace
   kubectl get secret <secret-name> -n <source-namespace> -o yaml > /tmp/secret.yaml

   # Edit namespace in file
   # Apply to target namespace
   kubectl apply -f /tmp/secret.yaml -n <target-namespace>
   ```

---

## Database Issues

### Database Connection Failures

**Symptoms**:

- Application cannot connect to database
- Connection timeout errors
- Authentication failures

**Diagnosis**:

```bash
# Check PostgreSQL pods
kubectl get pods -n postgresql

# Check PostgreSQL service
kubectl get svc -n postgresql

# Check database secrets
kubectl get secrets -n postgresql | grep db

# Test connection
kubectl run -it --rm psql-test --image=postgres:16 --restart=Never --env="PGPASSWORD=$(kubectl get secret <db-secret> -n postgresql -o jsonpath='{.data.password}' | base64 -d)" -- psql -h postgresql -U <user> -d <database>
```

**Resolution**:

1. **Verify Database Pod**:

   ```bash
   # Check PostgreSQL is running
   kubectl get pods -n postgresql

   # Check logs
   kubectl logs -n postgresql <postgresql-pod-name>
   ```

2. **Verify Database Secret**:

   ```bash
   # Check secret exists
   kubectl get secret <db-secret> -n postgresql

   # Verify secret keys
   kubectl get secret <db-secret> -n postgresql -o jsonpath='{.data}' | jq 'keys'
   ```

3. **Check Database Exists**:

   ```bash
   # Connect to PostgreSQL
   kubectl exec -it -n postgresql <postgresql-pod-name> -- psql -U postgres -l

   # Check if database exists
   kubectl exec -it -n postgresql <postgresql-pod-name> -- psql -U postgres -c "\l" | grep <database-name>
   ```

4. **Create Database** (if missing):

   ```bash
   # Run database creation job
   kubectl apply -f apps/postgresql/jobs/<app>-db-create-job.yaml

   # Check job status
   kubectl get jobs -n postgresql
   kubectl logs -n postgresql job/<app>-db-create
   ```

---

## Pod Issues

### Pod Stuck in Pending

**Symptoms**:

- Pod status: "Pending"
- Pod not starting

**Diagnosis**:

```bash
# Describe pod for details
kubectl describe pod <pod-name> -n <namespace>

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <pod-name>

# Check node resources
kubectl describe node <node-name>
```

**Common Causes**:

1. Insufficient node resources
2. No nodes matching node selector
3. PVC not binding
4. Taints/tolerations mismatch

**Resolution**:

1. **Check Resource Availability**:

   ```bash
   # Check node resources
   kubectl top nodes
   kubectl describe node <node-name> | grep -A 5 "Allocated resources"
   ```

2. **Check Node Selector**:

   ```bash
   # Check pod node selector
   kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.nodeSelector}'

   # Check if nodes match
   kubectl get nodes --show-labels | grep <selector-key>=<selector-value>
   ```

3. **Check PVC**:

   ```bash
   # Verify PVC is bound
   kubectl get pvc -n <namespace>
   kubectl describe pvc <pvc-name> -n <namespace>
   ```

### Pod Stuck in ContainerCreating

**Symptoms**:

- Pod status: "ContainerCreating"
- Pod not reaching Running state

**Diagnosis**:

```bash
# Describe pod
kubectl describe pod <pod-name> -n <namespace>

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <pod-name>

# Check volume attachments
kubectl get volumeattachment
```

**Common Causes**:

1. Volume mount failures
2. Image pull failures
3. Init container failures

**Resolution**:

1. **Check Volume Mounts**:

   ```bash
   # Check for volume mount errors in events
   kubectl describe pod <pod-name> -n <namespace> | grep -i "volume\|mount"
   ```

2. **Check Image Pull**:

   ```bash
   # Check for image pull errors
   kubectl describe pod <pod-name> -n <namespace> | grep -i "image\|pull"
   ```

3. **Check Init Containers**:

   ```bash
   # Check init container status
   kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.initContainerStatuses}'
   ```

### Pod CrashLoopBackOff

**Symptoms**:

- Pod status: "CrashLoopBackOff"
- Pod repeatedly crashing

**Diagnosis**:

```bash
# View pod logs
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous

# Describe pod
kubectl describe pod <pod-name> -n <namespace>

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <pod-name>
```

**Common Causes**:

1. Application configuration errors
2. Missing secrets or configmaps
3. Database connection failures
4. Resource limits too low

**Resolution**:

1. **Check Logs**:

   ```bash
   # View current logs
   kubectl logs <pod-name> -n <namespace> --tail=100

   # View previous container logs
   kubectl logs <pod-name> -n <namespace> --previous --tail=100
   ```

2. **Check Configuration**:

   ```bash
   # Verify secrets and configmaps exist
   kubectl get secrets,configmaps -n <namespace>
   ```

3. **Check Resource Limits**:

   ```bash
   # Check if OOMKilled
   kubectl describe pod <pod-name> -n <namespace> | grep -i "oom\|memory"
   ```

---

## Node Reboot Procedures

### Single Node Reboot

**Procedure**:

1. **Drain Node** (if possible):

   ```bash
   kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
   ```

2. **Reboot Node**

3. **Uncordon Node**:

   ```bash
   kubectl uncordon <node-name>
   ```

4. **Verify Pods**:

   ```bash
   kubectl get pods -A -o wide | grep <node-name>
   ```

### Multiple Node Reboot (Sequential)

**Recommended Sequence**:

1. **Reboot Worker Nodes First**:
   - Reboot one worker at a time
   - Wait for pods to reschedule
   - Verify cluster stability

2. **Reboot Master Node Last**:
   - Ensure all worker nodes are healthy
   - Reboot master node

3. **Verify Cluster**:

   ```bash
   kubectl get nodes
   kubectl get pods -A
   ```

### Full Cluster Reboot (Emergency)

**Procedure**:

1. **Stop ArgoCD Auto-Sync** (if enabled):

   ```bash
   # Disable auto-sync on all applications
   # Or scale down ArgoCD
   kubectl scale deployment argocd-application-controller -n argocd --replicas=0
   ```

2. **Scale Down Stateful Applications**:

   ```bash
   # Scale down apps with persistent storage
   kubectl scale deployment <app> -n <namespace> --replicas=0
   ```

3. **Wait for Longhorn Volumes to Detach**:
   - Check Longhorn UI
   - Verify all volumes are detached

4. **Reboot All Nodes**

5. **Wait for Cluster Stabilization** (5-10 minutes)

6. **Verify Cluster Health**:

   ```bash
   kubectl get nodes
   kubectl get pods -A
   ```

7. **Restart Stuck Pods** (if needed):

   ```bash
   # Delete stuck pods (they will be recreated)
   kubectl delete pod <pod-name> -n <namespace>
   ```

8. **Re-enable ArgoCD**:

   ```bash
   kubectl scale deployment argocd-application-controller -n argocd --replicas=1
   ```

### Common Issues After Reboots

**Longhorn Volume Mount Failures**:

```bash
# Check for stale volume attachments
kubectl get volumeattachment | grep <node-name>

# Restart Longhorn CSI plugin
kubectl delete pod -n longhorn-system -l app=longhorn-csi-plugin --field-selector spec.nodeName=<node-name>

# If issue persists, detach volume manually
kubectl scale deployment <app> -n <namespace> --replicas=0
# Wait for volume to detach
kubectl scale deployment <app> -n <namespace> --replicas=1
```

**Pod Stuck in Pending/ContainerCreating**:

```bash
# Check pod events
kubectl describe pod <pod-name> -n <namespace>

# Common causes:
# - Volume not detached from previous node
# - Node resources exhausted
# - Image pull failures
```

---

## Emergency Procedures

### Application Rollback

**Via ArgoCD**:

```bash
# View history
argocd app history <app-name>

# Rollback to previous version
argocd app rollback <app-name> <revision>
```

**Via Git**:

```bash
# Revert commit
git revert <commit-hash>
git push origin main

# Or checkout previous version
git checkout <commit-hash> -- apps/<app-name>
git commit -m "Rollback <app-name> to <commit-hash>"
git push origin main
```

### Cluster Recovery

**If ArgoCD is Down**:

1. **Check ArgoCD Pods**:

   ```bash
   kubectl get pods -n argocd
   ```

2. **Restart ArgoCD**:

   ```bash
   kubectl delete pod -n argocd -l app.kubernetes.io/name=argocd-application-controller
   ```

3. **Manual Apply** (if needed):

   ```bash
   # Apply app-of-apps manually
   kubectl apply -f argocd/app-of-apps.yaml
   ```

### Data Recovery

**From Longhorn Backups**:

1. **Access Longhorn UI**

2. **Restore Volume from Backup**:
   - Navigate to Backups
   - Select backup
   - Restore to new volume

3. **Update PVC** (if needed):

   ```bash
   # Update PVC to use restored volume
   kubectl edit pvc <pvc-name> -n <namespace>
   ```

---

## Common Error Messages

### "repository not accessible"

**Cause**: ArgoCD cannot access Git repository

**Resolution**:

```bash
# Check repository configuration
argocd repo list
argocd repo get <repo-url>

# Refresh repository
argocd repo get <repo-url> --refresh
```

### "sync failed: one or more objects failed to apply"

**Cause**: Invalid manifest or resource conflict

**Resolution**:

```bash
# Validate kustomization
kubectl kustomize apps/<app-name>

# Check for conflicts
kubectl get application <app-name> -n argocd -o yaml | grep -A 10 "status"
```

### "secret not found"

**Cause**: Secret not created or wrong namespace

**Resolution**:

```bash
# Check if secret exists
kubectl get secrets -n <namespace>

# Check SealedSecret
kubectl get sealedsecrets -n <namespace>

# Verify namespace matches
```

### "volume mount failed"

**Cause**: Longhorn volume not attached or multipathd conflict

**Resolution**:

- See [Storage Issues](#storage-issues)
- Check multipathd configuration
- Restart Longhorn CSI plugin

### "certificate order failed"

**Cause**: DNS challenge failed or API credentials invalid

**Resolution**:

- See [Certificate Issues](#certificate-issues)
- Verify DNS propagation
- Check Cloudflare API secret

---

## Related Documentation

- [Architecture Documentation](./ARCHITECTURE.md) - System architecture
- [Application Development Guide](./APPLICATION_DEVELOPMENT.md) - Adding
  applications
- [Platform Components](./PLATFORM_COMPONENTS.md) - Platform component details
- [Security](./SECURITY.md) - Security best practices
- [Main README](../README.md) - Repository overview

---

## See Also

- [ArgoCD Troubleshooting][argocd-troubleshooting]
- [Kubernetes Troubleshooting](https://kubernetes.io/docs/tasks/debug/)
- [Longhorn Troubleshooting](https://longhorn.io/docs/troubleshooting/)
- [Cert-Manager Troubleshooting](https://cert-manager.io/docs/troubleshooting/)

[argocd-troubleshooting]: https://argo-cd.readthedocs.io/en/stable/operator-manual/troubleshooting/
