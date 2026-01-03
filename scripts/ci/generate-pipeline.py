#!/usr/bin/env python3
"""
Generate dynamic GitLab CI child pipeline based on detected changes.

This script analyzes changed files and generates validation jobs
only for the affected applications and infrastructure components.
"""

import os
import sys
import yaml
import subprocess
from pathlib import Path
from typing import Any, Dict, List


def get_changed_files() -> List[str]:
    """Get list of changed files based on pipeline source."""
    pipeline_source = os.getenv("CI_PIPELINE_SOURCE", "")
    before_sha = os.getenv("CI_COMMIT_BEFORE_SHA", "")
    commit_sha = os.getenv("CI_COMMIT_SHA", "")

    try:
        if pipeline_source == "merge_request_event":
            target_branch = os.getenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "main")
            subprocess.run(
                ["git", "fetch", "origin", target_branch],
                check=True,
                capture_output=True,
                timeout=30,
            )
            result = subprocess.run(
                ["git", "diff", "--name-only", f"origin/{target_branch}...HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        elif before_sha and before_sha != "0000000000000000000000000000000000000000":
            result = subprocess.run(
                ["git", "diff", "--name-only", before_sha, commit_sha],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        else:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

        return [f.strip() for f in result.stdout.split("\n") if f.strip()]
    except subprocess.TimeoutExpired as e:
        print(f"Timeout getting changed files: {e}", file=sys.stderr)
        return []
    except subprocess.CalledProcessError as e:
        print(f"Error getting changed files: {e}", file=sys.stderr)
        return []


def find_all_manifests() -> Dict[Path, Dict[str, Any]]:
    """Find all directories containing kustomization.yaml files."""
    manifests: Dict[Path, Dict[str, Any]] = {}

    for directory in ["apps", "infrastructure", "argocd"]:
        if os.path.isdir(directory):
            for root, _dirs, files in os.walk(directory):
                if "_archive" in root:
                    continue

                if "kustomization.yaml" in files:
                    manifest_path = Path(root)
                    manifests[manifest_path] = {
                        "has_kustomization": True,
                        "files": set(),
                    }

    return manifests


def get_affected_manifests(changed_files: List[str]) -> Dict[Path, Dict[str, Any]]:
    """
    Determine which manifest directories are affected by the changes.
    Returns a dict keyed by manifest directory with metadata on whether a kustomization is present
    and which source files triggered the entry (useful for non-kustomize ArgoCD manifests).
    """
    affected: Dict[Path, Dict[str, Any]] = {}

    for file_path in changed_files:
        path = Path(file_path)

        if path.parts and path.parts[0] in ["apps", "infrastructure", "argocd"]:
            if "_archive" in file_path:
                continue

            # Walk up directory tree to find kustomization.yaml
            current = path.parent
            kustomization_dir = None
            while current != Path("."):
                if (current / "kustomization.yaml").exists():
                    kustomization_dir = current
                    break
                current = current.parent

            if kustomization_dir:
                manifest_dir = kustomization_dir
                has_kustomization = True
            else:
                # No kustomization found - validate raw manifests
                manifest_dir = path.parent if path.parent != Path(".") else Path(".")
                has_kustomization = False

            entry = affected.setdefault(
                manifest_dir, {"has_kustomization": has_kustomization, "files": set()}  # type: ignore
            )
            entry["has_kustomization"] = entry["has_kustomization"] or has_kustomization
            entry["files"].add(str(path))  # type: ignore

    return affected


def generate_validation_job(
    manifest_dir: Path, job_type: str, source_files: List[str] | None = None
) -> Dict[str, Any]:
    """Generate a validation job configuration for a manifest directory."""
    job_name = str(manifest_dir).replace("/", "-")

    if str(manifest_dir).startswith("apps/"):
        component_type = "app"
    elif str(manifest_dir).startswith("infrastructure/"):
        component_type = "infrastructure"
    else:
        component_type = "argocd"

    job_config: Dict[str, Any] = {
        "stage": "validate",
        "image": "${CI_IMAGE}",
        "tags": ["docker"],
        "before_script": [
            # Authenticate to GitLab Container Registry for private Helm chart pulls
            # Use 'docker login' (not 'helm registry login') so config saves to $DOCKER_CONFIG/config.json
            # Helm can read Docker's config format; helm-wrapper.sh copies it to Helm's isolated environment
            "export DOCKER_CONFIG=${CI_PROJECT_DIR}/.docker",
            "mkdir -p $DOCKER_CONFIG",
            'echo "$CI_REGISTRY_PASSWORD" | docker login "${CI_REGISTRY}" -u "${CI_REGISTRY_USER}" --password-stdin',
        ],
        "variables": {
            "MANIFEST_DIR": str(manifest_dir),
            "COMPONENT_TYPE": component_type,
            "WRAPPER_HELM_CONFIG": "${CI_PROJECT_DIR}/.docker/config.json",
        },
    }

    if job_type == "validate-kustomize":
        job_config["script"] = [
            f'echo "=========================================="',
            f'echo "Validating: {manifest_dir}"',
            f'echo "=========================================="',
            f'echo "Step 1: Kustomize build"',
            f"kustomize build {manifest_dir} --enable-helm --helm-command {os.getcwd()}/scripts/ci/helm-wrapper.sh | tee /tmp/manifests.yaml",
            'echo "✓ Kustomize build successful"',
            'echo ""',
            f'echo "Step 2: Kubernetes schema validation"',
            "cat /tmp/manifests.yaml | kubeconform "
            "-kubernetes-version ${KUBERNETES_VERSION} "
            "-schema-location default "
            "-schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' "
            "-summary -output json -ignore-missing-schemas -strict",
            'echo "✓ Schema validation successful"',
            'echo "=========================================="',
        ]

    elif job_type == "validate-raw":
        files_arg = " ".join(sorted(source_files or []))
        job_config["script"] = [
            f'echo "=========================================="',
            f'echo "Validating raw manifests: {manifest_dir}"',
            f'echo "=========================================="',
            "kubeconform "
            "-kubernetes-version ${KUBERNETES_VERSION} "
            "-schema-location default "
            "-schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' "
            "-summary -output json -ignore-missing-schemas -strict "
            f"{files_arg}",
            'echo "✓ Schema validation successful"',
            'echo "=========================================="',
        ]

    return {f"{job_type}:{job_name}": job_config}


def generate_child_pipeline(manifests: Dict[Path, Dict[str, Any]]) -> Dict[str, Any]:
    """Generate the complete child pipeline configuration."""
    pipeline: Dict[str, Any] = {
        "variables": {
            "CI_IMAGE": "${CI_IMAGE}",
            "KUBERNETES_VERSION": "${KUBERNETES_VERSION}",
            "KUSTOMIZE_VERSION": "${KUSTOMIZE_VERSION}",
            "KUBECONFORM_VERSION": "${KUBECONFORM_VERSION}",
            "CI_REGISTRY": "${CI_REGISTRY}",
            "CI_REGISTRY_USER": "${CI_REGISTRY_USER}",
            "CI_REGISTRY_PASSWORD": "${CI_REGISTRY_PASSWORD}",
        },
        "stages": ["validate"],
    }

    if not manifests:
        pipeline["no-changes"] = {
            "stage": "validate",
            "image": "${CI_IMAGE}",
            "tags": ["docker"],
            "script": ["echo 'No manifest changes detected - validation skipped'"],
        }
        return pipeline

    for manifest_dir in sorted(manifests):
        manifest_info = manifests[manifest_dir]
        has_kustomization = manifest_info["has_kustomization"]
        files_set = manifest_info["files"]
        source_files = (
            list(files_set)  # type: ignore
            if files_set
            else None
        )

        if has_kustomization:
            pipeline.update(generate_validation_job(manifest_dir, "validate-kustomize"))
        elif source_files:
            pipeline.update(
                generate_validation_job(
                    manifest_dir, "validate-raw", source_files=source_files
                )
            )

    return pipeline


def main():
    """Main entry point."""
    print("=" * 60, file=sys.stderr)
    print("Generating Dynamic Pipeline", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    changed_files = get_changed_files()
    print(f"\nChanged files ({len(changed_files)}):", file=sys.stderr)
    for f in changed_files[:10]:
        print(f"  - {f}", file=sys.stderr)
    if len(changed_files) > 10:
        print(f"  ... and {len(changed_files) - 10} more", file=sys.stderr)

    affected_manifests: Dict[Path, Dict[str, Any]]
    if changed_files:
        affected_manifests = get_affected_manifests(changed_files)
    else:
        print("\nNo changes detected, validating all manifests", file=sys.stderr)
        affected_manifests = find_all_manifests()

    print(f"\nAffected manifests ({len(affected_manifests)}):", file=sys.stderr)
    for manifest in sorted(affected_manifests):
        print(f"  - {manifest}", file=sys.stderr)

    child_pipeline = generate_child_pipeline(affected_manifests)
    child_pipeline["workflow"] = {"rules": [{"when": "always"}]}

    # Safety check: pipeline must have at least one job
    if len(child_pipeline) <= 3:
        print("WARNING: Pipeline was empty! Injecting fallback job.", file=sys.stderr)
        child_pipeline["fallback-job"] = {
            "stage": "validate",
            "image": "${CI_IMAGE}",
            "tags": ["docker"],
            "script": [
                "echo 'Fallback job - something went wrong with pipeline generation'"
            ],
        }

    output_file = "child-pipeline.yml"
    with open(output_file, "w") as f:
        f.write("---\n")
        yaml.dump(
            child_pipeline,
            f,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
            width=1000,
            allow_unicode=True,
            explicit_start=False,
        )

    print("\n" + "=" * 60, file=sys.stderr)
    print(f"Generated Child Pipeline ({output_file}):", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    with open(output_file, "r") as f:
        print(f.read(), file=sys.stderr)

    print("-" * 60, file=sys.stderr)
    print(
        f"\n✓ Generated pipeline with {len(child_pipeline) - 3} validation jobs",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
