# Contributing to ArgoCD Homelab

Thank you for your interest in contributing! This project is a portfolio
demonstration of GitOps best practices and infrastructure-as-code principles.
While it's primarily a personal project, I welcome contributions that improve
documentation, fix bugs, or enhance the overall quality.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Contribution Workflow](#contribution-workflow)
- [Style Guidelines](#style-guidelines)
- [Commit Message Conventions](#commit-message-conventions)

## Code of Conduct

This project follows a simple principle: **Be respectful and constructive**.
We're all here to learn and improve.

## How Can I Contribute?

### Reporting Issues

If you find a bug, documentation error, or have a suggestion:

1. **Check existing issues** to avoid duplicates
2. **Create a new issue** with:
   - Clear, descriptive title
   - Detailed description of the problem or suggestion
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Environment details (if applicable)

### Suggesting Enhancements

Enhancement suggestions are welcome! Please provide:

- **Use case**: Why this enhancement would be useful
- **Proposed solution**: How you envision it working
- **Alternatives**: Any alternative approaches you've considered

### Pull Requests

I welcome pull requests for:

- Documentation improvements
- Bug fixes
- Architecture enhancements
- New application examples
- Workflow improvements

## Development Setup

### Prerequisites

- Kubernetes cluster (local or remote)
- `kubectl` configured
- `helm` v4.x
- `kustomize` v5.x
- ArgoCD CLI (optional but recommended)
- Go 1.25+ (for kryptos development)

### Local Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/argo-apps.git
cd argo-apps

# Validate manifests before applying
kubectl apply -k apps/<app-name> --dry-run=server

# Test Helm chart rendering
helm template <app-name> oci://registry.example.com/homelab/helm-charts/<chart-name> \
  -f apps/<app-name>/values.yaml
```

## Contribution Workflow

1. **Fork the repository**

2. **Create a feature branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow existing patterns and conventions
   - Update documentation if needed
   - Test your changes locally

4. **Validate your changes**

   ```bash
   # Validate Kubernetes manifests
   kubectl apply -k apps/<app-name> --dry-run=server

   # Check for common issues
   kubectl diff -k apps/<app-name>
   ```

5. **Commit with meaningful messages** (see [Commit
   Conventions](#commit-message-conventions))

6. **Push to your fork**

   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**
   - Reference any related issues
   - Describe what changed and why
   - Include before/after examples if applicable

## Style Guidelines

### Kubernetes Manifests

- **Use `kustomization.yaml`** for all deployments
- **Follow naming conventions** documented in
  [docs/NAMING_CONVENTIONS.md](docs/NAMING_CONVENTIONS.md)
- **Namespace = Directory name** (except for infrastructure components)
- **Secrets**: Always use SealedSecrets, never plain secrets
- **Labels**: Include standard labels (`app.kubernetes.io/name`,
  `app.kubernetes.io/component`, etc.)

### Helm Charts

- Reference existing charts from the OCI registry when possible
- Use `values.yaml` for configuration
- Document all values with comments

### Directory Structure

```text
apps/<app-name>/
├── kustomization.yaml    # Required
├── values.yaml           # For Helm deployments
├── ingress/              # Traefik IngressRoute
│   └── ingress-route.yaml
└── secrets/              # SealedSecrets
    └── <app>-sealed-secret.yaml
```

### Documentation

- Use Markdown for all documentation
- Include code examples where helpful
- Update the main README if adding significant features
- Keep line length reasonable (~120 characters max)
- Use proper headings hierarchy

## Commit Message Conventions

Follow conventional commit format:

```text
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `chore`: Maintenance tasks
- `test`: Testing improvements

### Examples

```text
feat(apps): add affine collaborative editor

- Add Affine application with custom Helm chart
- Configure ingress route with TLS
- Add SealedSecret for database credentials

Closes #123
```

```text
docs(README): update app count to 11

Remove references to archived joplin and transcribe apps.
Update badges and application table.
```

```text
fix(traefik): correct middleware reference in ingress

The middleware namespace was incorrect, causing 404 errors.
Updated to use proper cross-namespace reference.
```

## Testing Requirements

Before submitting a PR:

1. **Validate all manifests**

   ```bash
   kubectl apply -k <path> --dry-run=server
   ```

2. **Test in a local cluster** (if possible)
   - Kind, k3s, or Minikube recommended
   - Verify the application deploys successfully
   - Check logs for errors

3. **Update documentation** if you changed:
   - Application structure
   - Deployment workflow
   - Prerequisites

## Recognition

Contributors will be acknowledged in:

- Pull request comments
- Release notes (for significant contributions)
- A future CONTRIBUTORS.md file

## Questions?

Feel free to:

- Open an issue for discussion
- Reach out via the project's GitHub Discussions
- Check existing documentation in the [docs/](docs/) folder

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.

---

Thank you for helping improve this project! 🚀
