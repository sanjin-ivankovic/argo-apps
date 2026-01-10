#!/usr/bin/env python3
"""
Markdown Linting

Validates Markdown documents using markdownlint for consistency and style.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

# Constants
CHECK_TIMEOUT = 5
LINT_TIMEOUT = 120
IGNORED_PATTERNS = ["node_modules", "charts", "**/charts"]


class MarkdownLinter:
    """Markdown linting with markdownlint."""

    def __init__(self, verbose: bool = False, fail_on_error: bool = False):
        self.verbose = verbose
        self.fail_on_error = fail_on_error
        self.project_root = Path(__file__).parent.parent.parent

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(message)

    def _build_command(self) -> List[str]:
        """Build markdownlint-cli2 command (auto-picks up .markdownlint-cli2.jsonc)."""
        return ["markdownlint-cli2", "**/*.md"]

    def check_markdownlint_available(self) -> bool:
        """Check if markdownlint-cli2 is installed."""
        import shutil

        return shutil.which("markdownlint-cli2") is not None

    def run_markdownlint(self) -> int:
        """
        Run markdownlint on all Markdown files.

        Returns:
            Exit code (0 = success, non-zero = failures or warning)
        """
        print("=" * 60)
        print("Running Markdown Linting")
        print("=" * 60)

        # Check if markdownlint is available
        if not self.check_markdownlint_available():
            print("\n⚠️  markdownlint-cli2 not installed (optional)")
            print("Install with: npm install -g markdownlint-cli2")
            # Return 0 since it's optional
            return 0

        # Get version
        try:
            version_check = subprocess.run(
                ["markdownlint-cli2", "--version"],
                capture_output=True,
                text=True,
                timeout=CHECK_TIMEOUT,
            )
            if version_check.returncode == 0:
                self.log(f"markdownlint-cli2 version: {version_check.stdout.strip()}")
        except Exception:
            pass

        cmd = self._build_command()
        self.log(f"Running: {' '.join(cmd)}")

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
                print("✅ Markdown linting passed")
            else:
                if self.fail_on_error:
                    print("❌ Markdown linting failed")
                else:
                    print("⚠️  Markdown linting found issues (not failing)")
            print("=" * 60)

            # Return 0 if we don't want to fail on errors (warning mode)
            return result.returncode if self.fail_on_error else 0

        except subprocess.TimeoutExpired:
            print(
                f"Error: markdownlint timed out after {LINT_TIMEOUT} seconds",
                file=sys.stderr,
            )
            return 1 if self.fail_on_error else 0
        except Exception as e:
            print(f"Error running markdownlint: {e}", file=sys.stderr)
            return 1 if self.fail_on_error else 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Markdown linting with markdownlint"
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Fail pipeline on markdown issues (default: warning only)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    linter = MarkdownLinter(verbose=args.verbose, fail_on_error=args.fail_on_error)
    return linter.run_markdownlint()


if __name__ == "__main__":
    sys.exit(main())
