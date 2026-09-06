#!/usr/bin/env python3
"""
Detect which apps/<tier>/<X> dirs were touched in the current commit
range. Output: JSON array of relative paths
(e.g. ["apps/user/litellm", "apps/infra/longhorn"]).

Apps are grouped under apps/<tier>/<name>/ where <tier> is one of
infra | data | services | user. Each <name> dir is one validatable app
(it has its own kustomization.yaml).

Consumed by the GitLab CI `validate:apps` job, which runs validate_app.py
once per array entry.

Environment variables (any of these can drive the diff range):
  CI_COMMIT_BEFORE_SHA   Previous commit on the branch (GitLab convention)
  CI_COMMIT_SHA          Current commit
If unset, falls back to HEAD~1..HEAD (works for normal pushes; degrades
to "list every app" on shallow clones where HEAD~1 doesn't exist).

Usage:
  python3 .ci/scripts/detect_apps.py             # prints JSON to stdout
  python3 .ci/scripts/detect_apps.py --output X  # also writes to file X
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Root that holds the tier dirs. Each apps/<tier>/<name> is one
# validatable app — i.e. has its own kustomization.yaml.
APPS_ROOT = "apps"


def changed_files() -> list[str]:
    before = os.getenv("CI_COMMIT_BEFORE_SHA", "")
    after = os.getenv("CI_COMMIT_SHA", "HEAD")
    if before and before != "0" * 40:
        cmd = ["git", "diff", "--name-only", before, after]
    else:
        # Shallow-clone fallback: try HEAD~1, else "everything changed"
        try:
            subprocess.run(
                ["git", "rev-parse", "HEAD~1"], check=True, capture_output=True
            )
            cmd = ["git", "diff", "--name-only", "HEAD~1", "HEAD"]
        except subprocess.CalledProcessError:
            return ["EVERYTHING"]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return [f.strip() for f in out.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError as e:
        print(f"git diff failed: {e}", file=sys.stderr)
        sys.exit(1)


def all_app_dirs() -> list[str]:
    """Every apps/<tier>/<name> dir that has a kustomization.yaml."""
    apps: list[str] = []
    root = Path(APPS_ROOT)
    if not root.is_dir():
        return apps
    for tier in sorted(root.iterdir()):
        if not tier.is_dir():
            continue
        for child in sorted(tier.iterdir()):
            if not child.is_dir():
                continue
            if (child / "kustomization.yaml").exists():
                apps.append(str(child))
    return apps


def affected_apps(files: list[str]) -> list[str]:
    """Map each changed file to its owning app dir."""
    apps = set()
    for f in files:
        p = Path(f)
        # `f` looks like `apps/user/litellm/values.yaml` — first 3
        # components (apps/<tier>/<name>) form the app dir.
        parts = p.parts
        if len(parts) < 4:
            continue
        if parts[0] != APPS_ROOT:
            continue
        app_dir = str(Path(parts[0]) / parts[1] / parts[2])
        if (Path(app_dir) / "kustomization.yaml").exists():
            apps.add(app_dir)
    return sorted(apps)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", help="Write JSON to this file in addition to stdout"
    )
    args = parser.parse_args()

    files = changed_files()
    if files == ["EVERYTHING"]:
        # Shallow clone with no HEAD~1 — validate all apps to be safe.
        result = all_app_dirs()
        print(
            f"[detect_apps] no HEAD~1 — falling back to all {len(result)} apps",
            file=sys.stderr,
        )
    else:
        result = affected_apps(files)
        print(
            f"[detect_apps] {len(files)} changed files → {len(result)} affected apps",
            file=sys.stderr,
        )

    payload = json.dumps(result)
    print(payload)
    if args.output:
        Path(args.output).write_text(payload + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
