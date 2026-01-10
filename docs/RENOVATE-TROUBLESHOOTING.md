# Renovate Troubleshooting Guide

## Issue: Renovate Runs But Creates No MRs/Issues

### Symptoms

- Renovate pipeline completes successfully
- Logs show dependencies found (e.g., `"depCount": 58`)
- Logs show `"result": "repository-changed"` or similar
- **No Merge Requests or Issues created**

### Root Cause

**Missing or invalid `RENOVATE_TOKEN` with write permissions.**

By default, GitLab CI provides a `CI_JOB_TOKEN` that Renovate can use for
authentication. However, this token has **read-only** access and **cannot
create Merge Requests or Issues**.

### Solution: Create and Configure RENOVATE_TOKEN

#### Step 1: Create a GitLab Token

You have two options:

#### Option A: Project Access Token (Recommended)

1. Go to your project: `Settings > Access Tokens`
2. Click `Add new token`
3. Configure:
   - **Token name**: `renovate-bot`
   - **Role**: `Maintainer` (required for creating MRs)
   - **Scopes**: Select `api` (this includes read/write repository access)
   - **Expiration**: Set to 1 year or never (if allowed)
4. Click `Create project access token`
5. **Copy the token immediately** (you won't see it again!)

#### Option B: Personal Access Token

1. Go to your user profile: `Preferences > Access Tokens`
2. Click `Add new token`
3. Configure:
   - **Token name**: `renovate-bot`
   - **Scopes**: Select `api`
   - **Expiration**: Set to 1 year
4. Click `Create personal access token`
5. **Copy the token immediately**

#### Step 2: Add Token to GitLab CI/CD Variables

1. Go to your project: `Settings > CI/CD > Variables`
2. Click `Add variable`
3. Configure:
   - **Key**: `RENOVATE_TOKEN`
   - **Value**: Paste the token you copied
   - **Type**: Variable
   - **Flags**:
     - ✅ **Protect variable**: Yes (only available on protected branches)
     - ✅ **Mask variable**: Yes (hide in logs)
     - ❌ **Expand variable reference**: No
4. Click `Add variable`

#### Step 3: Verify Configuration

Run a manual Renovate job with debug logging:

1. Go to `CI/CD > Pipelines`
2. Click `Run pipeline`
3. Select `main` branch
4. Click `Run pipeline`
5. Wait for the `renovate` job to appear
6. Click the play button (▶️) to run it manually
7. Check the logs

**Expected success indicators:**

```text
DEBUG: Using RENOVATE_TOKEN for authentication
DEBUG: Platform authentication successful
INFO: Creating merge request for dependency updates
```

**If still failing, check for:**

```text
WARN: Platform authentication failed
ERROR: Insufficient permissions
```

### Verification Checklist

- [ ] `RENOVATE_TOKEN` exists in CI/CD variables
- [ ] Token has `api` scope
- [ ] Token role is `Maintainer` (for Project Access Token)
- [ ] Token is not expired
- [ ] Variable is **Masked** but not **Expanded**
- [ ] Repository allows MR creation (not archived/locked)

### Additional Configuration

#### GitHub Release Data (Optional)

If you want Renovate to fetch release notes from GitHub repositories (for
charts hosted on GitHub), you can optionally add:

1. Create a GitHub Personal Access Token (classic):
   - Go to GitHub: `Settings > Developer settings > Personal access tokens >
Tokens (classic)`
   - Generate new token with `public_repo` scope
2. Add to GitLab CI/CD variables:
   - **Key**: `GITHUB_COM_TOKEN`
   - **Value**: Your GitHub token
   - **Flags**: Masked + Protected

This is **not required** for Renovate to work, but improves release notes in
MRs.

## Testing Renovate Locally (Advanced)

You can test Renovate locally to debug issues:

```bash
# Install Renovate CLI
npm install -g renovate

# Set environment variables
export RENOVATE_TOKEN="your-gitlab-token"
export RENOVATE_PLATFORM="gitlab"
export RENOVATE_ENDPOINT="https://git.example.com/api/v4"
export LOG_LEVEL="debug"

# Run Renovate (dry-run mode)
renovate --dry-run=full homelab/argo-apps
```

This will show you exactly what Renovate would do without making any changes.

## Common Errors

### Error: "Repository has changed during renovation - aborting"

This error is **misleading**. It often appears when:

- Authentication failed (missing/invalid token)
- Renovate cannot write to the repository
- Repository cache is stale

**Fix**: Ensure `RENOVATE_TOKEN` is properly configured with write permissions.

### Error: "Platform authentication failed"

**Cause**: Invalid or missing token
**Fix**:

1. Verify `RENOVATE_TOKEN` exists in CI/CD variables
2. Check token hasn't expired
3. Verify token has `api` scope

### Error: "Insufficient permissions to create merge request"

**Cause**: Token role is too low (e.g., `Developer` instead of `Maintainer`)
**Fix**: Recreate token with `Maintainer` role

## Further Reading

- [Renovate GitLab Platform
  Documentation](https://docs.renovatebot.com/modules/platform/gitlab/)
- [GitLab Project Access Tokens][gitlab-tokens]
- [Renovate Self-Hosted
  Configuration](https://docs.renovatebot.com/self-hosted-configuration/)

[gitlab-tokens]: https://docs.gitlab.com/ee/user/project/settings/project_access_tokens.html
