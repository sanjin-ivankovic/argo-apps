#!/usr/bin/env python3
"""
Validate one ArgoCD application directory by running:
  kustomize build --enable-helm <dir> | kubeconform -strict -summary

Renders the kustomize tree (including helmCharts inflation) and runs
kubeconform against the resulting manifest stream to catch:
  - kustomize build errors (missing files, broken patches, bad helm
    chart references, etc.)
  - kubernetes schema violations (missing required fields, wrong
    types, unknown kinds without skip-kinds)

Usage:
  python3 .ci/scripts/validate_app.py apps/user/litellm
  python3 .ci/scripts/validate_app.py apps/infra/longhorn
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# CRD schemas live in the datreeio/CRDs-catalog snapshot baked into the CI
# image at /opt/crds-catalog (see .ci/docker/Dockerfile, CRDS_CATALOG_REF).
# kubeconform reads them via -schema-location. The only kind we still skip
# is CustomResourceDefinition itself — kubeconform can't validate the
# embedded openAPIV3Schema fields shipped by upstream charts (argo-cd,
# cert-manager, etc.), and those CRDs are maintained by chart authors so
# re-validating them here adds no signal.
SKIP_KINDS = ["CustomResourceDefinition"]

# Local path the Dockerfile extracts the catalog snapshot into. Overridable
# via env for local dev (`CRDS_CATALOG_DIR=./vendor/crds-catalog python3
# validate_app.py …`) so contributors can validate without rebuilding the
# CI image.
DEFAULT_CRDS_CATALOG_DIR = "/opt/crds-catalog"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "app_dir",
        help="Path to an app directory containing kustomization.yaml",
    )
    parser.add_argument(
        "--kubernetes-version",
        # Single-sourced from the CI image (.ci/docker/Dockerfile sets
        # KUBECONFORM_KUBERNETES_VERSION from a Renovate-tracked ARG); the
        # literal fallback covers local runs outside the image.
        default=os.environ.get("KUBECONFORM_KUBERNETES_VERSION", "1.31.0"),
        help="Kubernetes API version kubeconform validates against",
    )
    args = parser.parse_args()

    app_path = Path(args.app_dir)
    if not (app_path / "kustomization.yaml").is_file():
        print(
            f"[validate_app] {app_path} has no kustomization.yaml — skipping",
            file=sys.stderr,
        )
        return 0

    print(f"=== {app_path} ===")

    # 1. kustomize build → captured manifest stream
    try:
        built = subprocess.run(
            ["kustomize", "build", "--enable-helm", str(app_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.CalledProcessError as e:
        print(f"kustomize build failed for {app_path}:", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        return 1

    # 2. kubeconform on the stdin manifest stream.
    # -schema-location is given twice: first the built-in catalog
    # (default = stock Kubernetes APIs), then the baked datreeio/CRDs-catalog
    # snapshot. kubeconform tries them in order — stock kinds resolve first,
    # CRDs fall through to the catalog. A missing schema becomes a hard
    # error (no silent skip) so a catalog regression surfaces immediately.
    catalog_dir = os.environ.get("CRDS_CATALOG_DIR", DEFAULT_CRDS_CATALOG_DIR)
    catalog_template = (
        f"{catalog_dir}/{{{{.Group}}}}/{{{{.ResourceKind}}}}_"
        "{{.ResourceAPIVersion}}.json"
    )
    skip_arg = ",".join(SKIP_KINDS)
    try:
        subprocess.run(
            [
                "kubeconform",
                "-strict",
                "-summary",
                "-kubernetes-version",
                args.kubernetes_version,
                "-schema-location",
                "default",
                "-schema-location",
                catalog_template,
                "-skip",
                skip_arg,
                "-",
            ],
            input=built.stdout,
            check=True,
            text=True,
            timeout=180,
        )
    except subprocess.CalledProcessError:
        print(f"kubeconform reported errors for {app_path}", file=sys.stderr)
        return 1

    print(f"OK {app_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
