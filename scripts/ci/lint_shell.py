#!/usr/bin/env python3
"""
Shell Script Linting

Validates shell scripts using shellcheck for best practices and common errors.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

# Constants
VERSION_CHECK_TIMEOUT = 5
LINT_TIMEOUT = 120
SKIP_DIRECTORIES = {"node_modules", ".git", "__pycache__", "venv", ".venv"}


class ShellLinter:
    """Shell script linting with shellcheck."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent.parent

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(message)

    def check_shellcheck_available(self) -> bool:
        """Check if shellcheck is installed."""
        return shutil.which("shellcheck") is not None

    def find_shell_scripts(self) -> List[Path]:
        """Find all shell scripts in the project."""
        shell_files: List[Path] = []

        # Find all .sh files, skip common directories
        for sh_file in self.project_root.rglob("*.sh"):
            # Skip if any part of path is in skip set (O(1) lookup)
            if not SKIP_DIRECTORIES.isdisjoint(sh_file.parts):
                continue
            shell_files.append(sh_file)

        return sorted(shell_files)

    def run_shellcheck(self) -> int:
        """
        Run shellcheck on all shell scripts.

        Returns:
            Exit code (0 = success, non-zero = failures)
        """
        print("=" * 60)
        print("Running Shell Script Linting")
        print("=" * 60)

        # Check if shellcheck is available
        if not self.check_shellcheck_available():
            print("Error: shellcheck not found or not executable", file=sys.stderr)
            print(
                "Install: https://github.com/koalaman/shellcheck#installing",
                file=sys.stderr,
            )
            return 1

        # Get version info
        try:
            version_check = subprocess.run(
                ["shellcheck", "--version"],
                capture_output=True,
                text=True,
                timeout=VERSION_CHECK_TIMEOUT,
                check=True,
            )
            # Extract version line
            version_line = next(
                (
                    line
                    for line in version_check.stdout.split("\n")
                    if line.startswith("version:")
                ),
                None,
            )
            if version_line:
                self.log(f"shellcheck {version_line}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"Warning: Could not get shellcheck version: {e}", file=sys.stderr)

        # Find shell scripts
        shell_files = self.find_shell_scripts()

        if not shell_files:
            print("\n✅ No shell scripts found to lint")
            return 0

        print(f"\nFound {len(shell_files)} shell script(s) to lint")
        if self.verbose:
            for script in shell_files:
                print(f"  - {script.relative_to(self.project_root)}")

        # Build command
        cmd = ["shellcheck"] + [str(f) for f in shell_files]

        self.log(f"\nRunning shellcheck on {len(shell_files)} files...")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=LINT_TIMEOUT,
            )

            # Print output
            if result.stdout:
                print("\n" + result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            # Print summary
            print("\n" + "=" * 60)
            if result.returncode == 0:
                print(f"✅ Shell linting passed ({len(shell_files)} files)")
            else:
                print(f"❌ Shell linting failed ({len(shell_files)} files)")
            print("=" * 60)

            return result.returncode

        except subprocess.TimeoutExpired:
            print(
                f"Error: shellcheck timed out after {LINT_TIMEOUT} seconds",
                file=sys.stderr,
            )
            return 1
        except Exception as e:
            print(f"Error running shellcheck: {e}", file=sys.stderr)
            return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run shell script linting with shellcheck"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    linter = ShellLinter(verbose=args.verbose)
    return linter.run_shellcheck()


if __name__ == "__main__":
    sys.exit(main())
