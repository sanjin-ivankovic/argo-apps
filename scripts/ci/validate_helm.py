#!/usr/bin/env python3
"""
Validate Helm chart configurations in Kustomize-managed applications.

This script iterates through apps/ directories, identifies those using Helm charts
via Kustomize, and validates the chart configurations by templating them with helm.
"""

import shutil
import subprocess
import sys
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

# Constants
DEFAULT_APPS_DIR = Path("apps")
KUSTOMIZATION_FILE = "kustomization.yaml"
VALUES_FILE = "values.yaml"
HELM_TIMEOUT = 60
HELM_CHARTS_KEY = "helmCharts"


class HelmValidator:
    """Validate Helm chart configurations."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.errors: List[str] = []
        self.validated_count = 0
        self.skipped_count = 0

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(message)

    def check_helm_available(self) -> bool:
        """Check if helm is installed."""
        return shutil.which("helm") is not None

    def find_helm_apps(self, apps_dir: Path = DEFAULT_APPS_DIR) -> List[Path]:
        """Find all apps that use Helm charts via Kustomize."""
        if not apps_dir.exists():
            return []

        helm_apps: List[Path] = []

        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir():
                continue

            kustomization_file = app_dir / KUSTOMIZATION_FILE
            if not kustomization_file.exists():
                continue

            try:
                with open(kustomization_file, "r") as f:
                    kustomization = yaml.safe_load(f)

                # Check if it has helmCharts defined
                if kustomization and HELM_CHARTS_KEY in kustomization:
                    helm_apps.append(app_dir)
            except yaml.YAMLError as e:
                self.log(f"⚠️  Warning: Could not parse {kustomization_file}: {e}")

        return helm_apps

    def extract_helm_config(self, app_dir: Path) -> Optional[Dict[str, Any]]:
        """Extract Helm chart configuration from kustomization.yaml."""
        kustomization_file = app_dir / KUSTOMIZATION_FILE

        try:
            with open(kustomization_file, "r") as f:
                kustomization = yaml.safe_load(f)

            if not kustomization or HELM_CHARTS_KEY not in kustomization:
                return None

            # Get first Helm chart (most apps have only one)
            helm_charts = kustomization.get(HELM_CHARTS_KEY, [])
            if not helm_charts:
                return None

            helm_config = helm_charts[0]

            values_path = app_dir / VALUES_FILE
            return {
                "repo": helm_config.get("repo", ""),
                "name": helm_config.get("name", ""),
                "version": helm_config.get("version", ""),
                "namespace": helm_config.get("namespace", app_dir.name),
                "values_file": values_path if values_path.exists() else None,
            }
        except Exception as e:
            self.log(f"⚠️  Warning: Could not extract Helm config from {app_dir}: {e}")
            return None

    def validate_helm_chart(self, app_name: str, config: Dict[str, Any]) -> bool:
        """Validate a Helm chart by templating it."""
        repo = config["repo"]
        chart_name = config["name"]
        version = config["version"]
        namespace = config["namespace"]
        values_file = config.get("values_file")

        print(f"\nValidating Helm configuration for {app_name}")
        self.log(f"  Chart: {chart_name} ({version}) from {repo}")

        if values_file:
            self.log(f"  Values: {values_file}")
        else:
            print("  ⚠️  No values.yaml found, skipping validation")
            self.skipped_count += 1
            return True

        # Build helm template command
        # For OCI registries, use full reference instead of --repo flag
        if repo.startswith("oci://"):
            # OCI format: oci://registry/path/chart:version
            chart_ref = f"{repo}/{chart_name}"
            cmd: List[str] = [
                "helm",
                "template",
                app_name,
                chart_ref,
                "--version",
                version,
                "--namespace",
                namespace,
            ]
        else:
            # Traditional HTTP(S) repo format
            cmd = [
                "helm",
                "template",
                app_name,
                chart_name,
                "--repo",
                repo,
                "--version",
                version,
                "--namespace",
                namespace,
            ]

        if values_file:
            cmd.extend(["--values", str(values_file)])

        try:
            # Run helm template to validate
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=HELM_TIMEOUT,
            )

            if result.returncode != 0:
                print(f"  ❌ Helm validation failed for {app_name}")
                print(f"  Error: {result.stderr}")
                first_error = (
                    result.stderr.split("\n", 1)[0]
                    if result.stderr
                    else "Unknown error"
                )
                self.errors.append(f"{app_name}: {first_error}")
                return False
            else:
                print(f"  ✅ Helm validation passed for {app_name}")
                self.validated_count += 1
                return True

        except subprocess.TimeoutExpired:
            print(f"  ❌ Helm validation timed out for {app_name}")
            self.errors.append(f"{app_name}: Validation timed out")
            return False
        except Exception as e:
            print(f"  ❌ Helm validation failed for {app_name}: {e}")
            self.errors.append(f"{app_name}: {str(e)}")
            return False

    def validate_all(self) -> int:
        """Validate all Helm chart configurations."""
        print("=" * 60)
        print("Running Helm Chart Validation")
        print("=" * 60)

        helm_apps = self.find_helm_apps()

        if not helm_apps:
            print("\n✅ No Helm-based applications found")
            return 0

        print(f"\nFound {len(helm_apps)} Helm-based application(s)")

        for app_dir in helm_apps:
            config = self.extract_helm_config(app_dir)

            if not config:
                continue

            self.validate_helm_chart(app_dir.name, config)

        # Print summary
        print("\n" + "=" * 60)
        print("Helm Validation Summary")
        print("=" * 60)
        print(f"Validated: {self.validated_count}")
        print(f"Skipped: {self.skipped_count}")
        print(f"Failed: {len(self.errors)}")

        if self.errors:
            print("\n❌ Errors:")
            for error in self.errors:
                print(f"  - {error}")
            return 1
        else:
            print("\n✅ All Helm charts validated successfully")
            return 0


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate Helm chart configurations in Kustomize-managed apps"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--apps-dir",
        type=Path,
        default=DEFAULT_APPS_DIR,
        help="Directory containing applications (default: apps)",
    )

    args = parser.parse_args()

    # Create validator instance
    validator = HelmValidator(verbose=args.verbose)

    # Check if helm is available
    if not validator.check_helm_available():
        print("Error: helm not found or not executable", file=sys.stderr)
        print("Please ensure helm is installed and in PATH", file=sys.stderr)
        print("Install: https://helm.sh/docs/intro/install/", file=sys.stderr)
        return 1

    return validator.validate_all()


if __name__ == "__main__":
    sys.exit(main())
