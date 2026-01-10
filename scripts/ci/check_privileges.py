#!/usr/bin/env python3
"""
Check Kubernetes manifests for security privilege escalations.

This script analyzes Kubernetes manifests built from Kustomize to detect
potential security issues like privileged containers, host access, and
dangerous capabilities. It only scans manifests that have changed to
improve performance.
"""

import os
import sys
import json
import subprocess
import yaml
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class SecurityFinding:
    """Represents a security finding in a manifest."""

    severity: str  # "high", "medium", "low"
    check: str
    manifest_dir: str
    resource_kind: str
    resource_name: str
    namespace: str
    details: str
    line_context: str = ""


class PrivilegeChecker:
    """Check Kubernetes manifests for privilege escalations."""

    # Constants
    SCAN_DIRECTORIES = ["apps", "infrastructure", "argocd"]
    GIT_TIMEOUT = 30
    BUILD_TIMEOUT = 60
    MAX_WORKERS = 4  # Parallel kustomize builds

    DANGEROUS_CAPABILITIES = [
        "SYS_ADMIN",
        "NET_ADMIN",
        "SYS_MODULE",
        "SYS_RAWIO",
        "SYS_PTRACE",
        "DAC_OVERRIDE",
    ]

    def __init__(self, changed_files: Optional[List[str]] = None):
        self.changed_files = changed_files or []
        self.findings: List[SecurityFinding] = []

    def get_changed_files(self) -> List[str]:
        """Get list of changed files from git."""
        if self.changed_files:
            return self.changed_files

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
                    timeout=self.GIT_TIMEOUT,
                )
                result = subprocess.run(
                    ["git", "diff", "--name-only", f"origin/{target_branch}...HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.GIT_TIMEOUT,
                )
            elif (
                before_sha and before_sha != "0000000000000000000000000000000000000000"
            ):
                result = subprocess.run(
                    ["git", "diff", "--name-only", before_sha, commit_sha],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.GIT_TIMEOUT,
                )
            else:
                result = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self.GIT_TIMEOUT,
                )

            return [f.strip() for f in result.stdout.split("\n") if f.strip()]
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"Warning: Could not get changed files: {e}", file=sys.stderr)
            return []

    def get_affected_kustomizations(self, changed_files: List[str]) -> Set[Path]:
        """Find kustomization directories affected by changes."""
        affected: Set[Path] = set()

        for file_path in changed_files:
            path = Path(file_path)

            # Only check relevant directories
            if not any(
                path.is_relative_to(d)
                for d in self.SCAN_DIRECTORIES
                if Path(d).exists()
            ):
                continue

            # Walk up to find kustomization.yaml
            current = path.parent
            while current != Path("."):
                if (current / "kustomization.yaml").exists():
                    affected.add(current)
                    break
                current = current.parent

        return affected

    def build_manifests(self, kustomize_dir: Path) -> str:
        """Build Kustomize manifests for a directory."""
        try:
            helm_wrapper = Path("scripts/ci/helm-wrapper.sh")
            helm_cmd = str(helm_wrapper.absolute()) if helm_wrapper.exists() else "helm"

            result = subprocess.run(
                [
                    "kustomize",
                    "build",
                    str(kustomize_dir),
                    "--enable-helm",
                    "--helm-command",
                    helm_cmd,
                ],
                capture_output=True,
                text=True,
                timeout=self.BUILD_TIMEOUT,
            )

            if result.returncode != 0:
                print(
                    f"Warning: Failed to build {kustomize_dir}: {result.stderr}",
                    file=sys.stderr,
                )
                return ""

            return result.stdout
        except subprocess.TimeoutExpired:
            print(f"Warning: Timeout building {kustomize_dir}", file=sys.stderr)
            return ""
        except Exception as e:
            print(f"Warning: Error building {kustomize_dir}: {e}", file=sys.stderr)
            return ""

    def parse_manifests(self, manifest_yaml: str) -> List[Dict[str, Any]]:
        """Parse YAML manifests into list of resources."""
        resources: List[Dict[str, Any]] = []
        try:
            for doc in yaml.safe_load_all(manifest_yaml):
                if doc and isinstance(doc, dict):
                    resources.append(doc)  # type: ignore[arg-type]
        except yaml.YAMLError as e:
            print(f"Warning: Failed to parse YAML: {e}", file=sys.stderr)
        return resources

    def check_resource(self, resource: Dict[str, Any], manifest_dir: Path):
        """Check a single resource for security issues."""
        kind = resource.get("kind", "Unknown")
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "unknown")
        namespace = metadata.get("namespace", "default")
        spec = resource.get("spec", {})

        # Only check Pod-like resources
        if kind not in [
            "Pod",
            "Deployment",
            "StatefulSet",
            "DaemonSet",
            "Job",
            "CronJob",
            "ReplicaSet",
        ]:
            return

        # Get pod template spec
        if kind == "Pod":
            pod_spec = spec
        else:
            pod_spec = spec.get("template", {}).get("spec", {})

        # Check security context at pod level
        pod_security_context = pod_spec.get("securityContext", {})

        # Check hostNetwork
        if pod_spec.get("hostNetwork"):
            self.findings.append(
                SecurityFinding(
                    severity="high",
                    check="hostNetwork",
                    manifest_dir=str(manifest_dir),
                    resource_kind=kind,
                    resource_name=name,
                    namespace=namespace,
                    details="Pod uses host network namespace",
                )
            )

        # Check hostPID
        if pod_spec.get("hostPID"):
            self.findings.append(
                SecurityFinding(
                    severity="high",
                    check="hostPID",
                    manifest_dir=str(manifest_dir),
                    resource_kind=kind,
                    resource_name=name,
                    namespace=namespace,
                    details="Pod uses host PID namespace",
                )
            )

        # Check hostIPC
        if pod_spec.get("hostIPC"):
            self.findings.append(
                SecurityFinding(
                    severity="medium",
                    check="hostIPC",
                    manifest_dir=str(manifest_dir),
                    resource_kind=kind,
                    resource_name=name,
                    namespace=namespace,
                    details="Pod uses host IPC namespace",
                )
            )

        # Check containers
        containers: List[Dict[str, Any]] = pod_spec.get(
            "containers", []
        ) + pod_spec.get("initContainers", [])

        for container in containers:
            container_name = container.get("name", "unknown")
            security_context = container.get("securityContext", {})

            # Check privileged
            if security_context.get("privileged"):
                self.findings.append(
                    SecurityFinding(
                        severity="high",
                        check="privileged",
                        manifest_dir=str(manifest_dir),
                        resource_kind=kind,
                        resource_name=f"{name}/{container_name}",
                        namespace=namespace,
                        details="Container runs in privileged mode",
                    )
                )

            # Check allowPrivilegeEscalation
            if security_context.get("allowPrivilegeEscalation", True):
                # Only flag if explicitly set to true (default is true, so we check if it's missing)
                if "allowPrivilegeEscalation" in security_context:
                    self.findings.append(
                        SecurityFinding(
                            severity="medium",
                            check="allowPrivilegeEscalation",
                            manifest_dir=str(manifest_dir),
                            resource_kind=kind,
                            resource_name=f"{name}/{container_name}",
                            namespace=namespace,
                            details="Container allows privilege escalation",
                        )
                    )

            # Check runAsNonRoot
            container_run_as_non_root = security_context.get("runAsNonRoot")
            pod_run_as_non_root = pod_security_context.get("runAsNonRoot")
            run_as_non_root = (
                container_run_as_non_root
                if container_run_as_non_root is not None
                else pod_run_as_non_root
            )
            if run_as_non_root is False:
                self.findings.append(
                    SecurityFinding(
                        severity="medium",
                        check="runAsRoot",
                        manifest_dir=str(manifest_dir),
                        resource_kind=kind,
                        resource_name=f"{name}/{container_name}",
                        namespace=namespace,
                        details="Container explicitly allows running as root",
                    )
                )

            # Check capabilities
            capabilities = security_context.get("capabilities", {})
            added_caps = capabilities.get("add", [])

            for cap in added_caps:
                if cap in self.DANGEROUS_CAPABILITIES:
                    self.findings.append(
                        SecurityFinding(
                            severity="high",
                            check="dangerousCapability",
                            manifest_dir=str(manifest_dir),
                            resource_kind=kind,
                            resource_name=f"{name}/{container_name}",
                            namespace=namespace,
                            details=f"Container adds dangerous capability: {cap}",
                        )
                    )

        # Check volumes for hostPath
        volumes = pod_spec.get("volumes", [])
        for volume in volumes:
            if "hostPath" in volume:
                host_path = volume["hostPath"].get("path", "unknown")
                self.findings.append(
                    SecurityFinding(
                        severity="high",
                        check="hostPath",
                        manifest_dir=str(manifest_dir),
                        resource_kind=kind,
                        resource_name=name,
                        namespace=namespace,
                        details=f"Pod mounts host path: {host_path}",
                    )
                )

    def build_and_check_kustomization(self, kustomize_dir: Path) -> int:
        """Build and check a single kustomization (for parallel execution)."""
        manifests_yaml = self.build_manifests(kustomize_dir)
        if not manifests_yaml:
            return 0

        resources = self.parse_manifests(manifests_yaml)
        for resource in resources:
            self.check_resource(resource, kustomize_dir)

        return len(resources)

    def check_all(self, scan_all: bool = False) -> int:
        """Check all affected manifests for security issues."""
        print("=" * 60)
        print("Checking for Kubernetes Security Issues")
        print("=" * 60)

        if scan_all:
            print("\nScanning ALL kustomizations...")
            kustomizations: Set[Path] = set()
            for directory in self.SCAN_DIRECTORIES:
                if os.path.isdir(directory):
                    for root, _dirs, files in os.walk(directory):
                        if "kustomization.yaml" in files:
                            kustomizations.add(Path(root))
        else:
            changed_files = self.get_changed_files()
            print(f"\nChanged files: {len(changed_files)}")
            if changed_files:
                for f in changed_files[:5]:
                    print(f"  - {f}")
                if len(changed_files) > 5:
                    print(f"  ... and {len(changed_files) - 5} more")

            kustomizations = self.get_affected_kustomizations(changed_files)

        print(f"\nKustomizations to scan: {len(kustomizations)}")
        for k in sorted(kustomizations):
            print(f"  - {k}")

        if not kustomizations:
            print("\nNo kustomizations to scan")
            return 0

        print("\n" + "=" * 60)
        print("Scanning manifests...")
        print("=" * 60)

        # Process kustomizations in parallel for better performance
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            # Submit all kustomizations for parallel processing
            future_to_dir = {
                executor.submit(self.build_and_check_kustomization, kdir): kdir
                for kdir in sorted(kustomizations)
            }

            # Collect results as they complete
            for future in as_completed(future_to_dir):
                kustomize_dir = future_to_dir[future]
                try:
                    num_resources = future.result()
                    if num_resources > 0:
                        print(f"✓ {kustomize_dir}: {num_resources} resources")
                except Exception as e:
                    print(f"✗ {kustomize_dir}: {e}", file=sys.stderr)
                    continue

        return len(self.findings)

    def print_report(self):
        """Print findings report."""
        print("\n" + "=" * 60)
        print("Security Check Results")
        print("=" * 60)

        if not self.findings:
            print("\n✅ No security concerns detected")
            return

        # Group by severity
        high = [f for f in self.findings if f.severity == "high"]
        medium = [f for f in self.findings if f.severity == "medium"]
        low = [f for f in self.findings if f.severity == "low"]

        print(f"\nFound {len(self.findings)} security findings:")
        print(f"  🔴 High:   {len(high)}")
        print(f"  🟡 Medium: {len(medium)}")
        print(f"  🟢 Low:    {len(low)}")

        for severity, findings in [("HIGH", high), ("MEDIUM", medium), ("LOW", low)]:
            if not findings:
                continue

            print(f"\n{severity} SEVERITY FINDINGS:")
            print("-" * 60)

            for finding in findings:
                print(f"\n  Check: {finding.check}")
                print(f"  Resource: {finding.resource_kind}/{finding.resource_name}")
                print(f"  Namespace: {finding.namespace}")
                print(f"  Location: {finding.manifest_dir}")
                print(f"  Details: {finding.details}")

    def save_json_report(self, output_file: str = "security-findings.json"):
        """Save findings as JSON report."""
        report: Dict[str, Any] = {
            "total_findings": len(self.findings),
            "high_severity": len([f for f in self.findings if f.severity == "high"]),
            "medium_severity": len(
                [f for f in self.findings if f.severity == "medium"]
            ),
            "low_severity": len([f for f in self.findings if f.severity == "low"]),
            "findings": [asdict(f) for f in self.findings],
        }

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 JSON report saved to: {output_file}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Check Kubernetes manifests for security issues"
    )
    parser.add_argument(
        "--all", action="store_true", help="Scan all kustomizations (not just changed)"
    )
    parser.add_argument("--json", type=str, help="Output JSON report to file")
    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        help="Exit with error if high severity findings",
    )

    args = parser.parse_args()

    checker = PrivilegeChecker()
    num_findings = checker.check_all(scan_all=args.all)
    checker.print_report()

    if args.json:
        checker.save_json_report(args.json)

    print("\n" + "=" * 60)

    # Determine exit code
    if args.fail_on_high:
        high_findings = sum(1 for f in checker.findings if f.severity == "high")
        if high_findings > 0:
            print(f"❌ Found {high_findings} high severity findings - failing")
            return 1

    if num_findings > 0:
        print(f"⚠️  Found {num_findings} findings - review recommended")
        return 0  # Don't fail, just warn
    else:
        print("✅ No security concerns detected")
        return 0


if __name__ == "__main__":
    sys.exit(main())
