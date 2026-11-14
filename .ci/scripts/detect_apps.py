#!/usr/bin/env python3
"""
Detect which apps/<tier>/<X> dirs were touched in the current commit
range. Output: JSON array of relative paths
(e.g. ["apps/user/memos", "apps/infra/longhorn"]).

Apps are grouped under apps/<tier>/<name>/ where <tier> is one of
infra | data | services | user. Each <name> dir is one validatable app
(it has its own kustomization.yaml).

Consumed by the GitLab CI `validate:apps` job, which runs validate_app.py
once per array entry.

Diff range, first match wins:
  CI_MERGE_REQUEST_DIFF_BASE_SHA..CI_COMMIT_SHA  MR pipelines (merge base of
      the MR, so every commit in the MR counts, not only the last one;
      CI_COMMIT_BEFORE_SHA is all zeros in MR pipelines)
  CI_COMMIT_BEFORE_SHA..CI_COMMIT_SHA            pushes to main
  HEAD~1..HEAD                                   local runs
A base commit missing from the shallow clone is fetched by SHA. When no
range can be built, every app is listed so nothing goes unvalidated.

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


ZERO_SHA = "0" * 40


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def have_commit(sha: str) -> bool:
    """True when sha is in the clone, fetching it by SHA if needed."""
    if git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0:
        return True
    git("fetch", "--quiet", "--depth=1", "origin", sha)
    return git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def diff_base() -> str | None:
    """The commit to diff against, or None when no usable base exists."""
    for var in ("CI_MERGE_REQUEST_DIFF_BASE_SHA", "CI_COMMIT_BEFORE_SHA"):
        sha = os.getenv(var, "")
        if sha and sha != ZERO_SHA:
            return sha if have_commit(sha) else None
    if git("rev-parse", "--verify", "--quiet", "HEAD~1").returncode == 0:
        return "HEAD~1"
    return None


def changed_files() -> list[str]:
    base = diff_base()
    if base is None:
        return ["EVERYTHING"]
    after = os.getenv("CI_COMMIT_SHA", "HEAD")
    out = git("diff", "--name-only", base, after)
    if out.returncode != 0:
        print(f"git diff {base} {after} failed: {out.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return [f.strip() for f in out.stdout.splitlines() if f.strip()]


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
        # `f` looks like `apps/user/memos/values.yaml` — first 3
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
        result = all_app_dirs()
        print(
            f"[detect_apps] no diff base — validating all {len(result)} apps",
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
