#!/usr/bin/env python3
"""
Validate ArgoCD Application and ApplicationSet manifests.

This script validates ArgoCD CRD manifests using kubeconform to ensure
they are syntactically correct and compatible with the ArgoCD CRD schemas.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Constants
ARGOCD_DIRS = ["argocd/applications", "argocd/infrastructure"]
MANIFEST_PATTERN = "*.yaml"
KUBECONFORM_TIMEOUT = 30
KUBECONFORM_VERSION_TIMEOUT = 10


class ArgoCDValidator:
    """Validate ArgoCD Application manifests."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.errors: List[Tuple[str, str]] = []  # (manifest_path, error_message)
        self.validated_count = 0

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(message)

    def check_kubeconform_available(self) -> bool:
        """Check if kubeconform is installed."""
        return shutil.which("kubeconform") is not None

    def find_argocd_manifests(self) -> List[Path]:
        """Find all ArgoCD Application and ApplicationSet manifests."""
        manifests: List[Path] = []

        for dir_path in ARGOCD_DIRS:
            directory = Path(dir_path)
            if directory.exists():
                manifests.extend(
                    f for f in directory.glob(MANIFEST_PATTERN) if f.is_file()
                )

        return sorted(manifests)

    def validate_manifest(self, manifest_path: Path) -> bool:
        """Validate a single ArgoCD manifest using kubeconform."""
        self.log(f"\nValidating {manifest_path}")

        try:
            # Use kubeconform to validate without needing a cluster
            result = subprocess.run(
                [
                    "kubeconform",
                    "-strict",
                    "-summary",
                    "-output",
                    "text",
                    str(manifest_path),
                ],
                capture_output=True,
                text=True,
                timeout=KUBECONFORM_TIMEOUT,
            )

            if result.returncode != 0:
                print(f"  ❌ Validation failed: {manifest_path.name}")
                error_msg = (
                    result.stdout.strip()
                    if result.stdout
                    else result.stderr.strip() if result.stderr else "Unknown error"
                )
                self.log(f"  Error: {error_msg}")
                self.errors.append((str(manifest_path), error_msg))
                return False
            else:
                print(f"  ✅ Valid: {manifest_path.name}")
                self.validated_count += 1
                return True

        except subprocess.TimeoutExpired:
            print(f"  ❌ Validation timed out: {manifest_path.name}")
            self.errors.append((str(manifest_path), "Validation timed out"))
            return False
        except Exception as e:
            print(f"  ❌ Validation error: {manifest_path.name}")
            self.log(f"  Exception: {e}")
            self.errors.append((str(manifest_path), str(e)))
            return False

    def validate_all(self) -> int:
        """Validate all ArgoCD manifests."""
        print("=" * 60)
        print("Validating ArgoCD Application Manifests")
        print("=" * 60)

        manifests = self.find_argocd_manifests()

        if not manifests:
            print("\n✅ No ArgoCD manifests found")
            return 0

        print(f"\nFound {len(manifests)} ArgoCD manifest(s)")

        for manifest in manifests:
            self.validate_manifest(manifest)

        # Print summary
        print("\n" + "=" * 60)
        print("ArgoCD Validation Summary")
        print("=" * 60)
        print(f"Validated: {self.validated_count}")
        print(f"Failed: {len(self.errors)}")

        if self.errors:
            print("\n❌ Validation Errors:")
            for manifest_path, error_msg in self.errors:
                print(f"\n  {manifest_path}:")
                # Print first line of error for brevity
                first_line = (
                    error_msg.split("\n", 1)[0] if error_msg else "Unknown error"
                )
                print(f"    {first_line}")

            return 1
        else:
            print("\n✅ All ArgoCD manifests validated successfully")
            return 0


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate ArgoCD Application and ApplicationSet manifests"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Create validator instance to use its method
    validator = ArgoCDValidator(verbose=args.verbose)

    # Check if kubeconform is available
    if not validator.check_kubeconform_available():
        print("Error: kubeconform not found or not executable", file=sys.stderr)
        print("Please ensure kubeconform is installed and in PATH", file=sys.stderr)
        print("Install: https://github.com/yannh/kubeconform", file=sys.stderr)
        return 1

    # Verify kubeconform works by checking version
    try:
        subprocess.run(
            ["kubeconform", "-v"],
            capture_output=True,
            timeout=KUBECONFORM_VERSION_TIMEOUT,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"Error: Could not execute kubeconform: {e}", file=sys.stderr)
        return 1

    return validator.validate_all()


if __name__ == "__main__":
    sys.exit(main())
