#!/usr/bin/env python3
"""
YAML Linting Script

Validates YAML syntax across all manifest files using yamllint.
Supports GitLab Code Quality JSON format output.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

# Constants
VERSION_CHECK_TIMEOUT = 5
LINT_TIMEOUT = 120

# Type alias for output formats
OutputFormat = Literal["standard", "parsable", "gitlab"]


class YAMLLinter:
    """YAML linting with yamllint."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent.parent

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(message)

    def check_yamllint_available(self) -> bool:
        """Check if yamllint is installed."""
        return shutil.which("yamllint") is not None

    def _build_command(self, output_format: OutputFormat) -> list[str]:
        """Build yamllint command with format option."""
        cmd = ["yamllint", ".", "--strict"]

        # yamllint doesn't support 'gitlab', use 'parsable' and convert
        if output_format == "gitlab":
            cmd.extend(["--format", "parsable"])
        elif output_format == "parsable":
            cmd.extend(["--format", "parsable"])

        return cmd

    def _convert_to_gitlab_format(self, parsable_output: str) -> str:
        """Convert yamllint parsable output to GitLab Code Quality JSON."""
        issues: list[dict[str, str | int | dict[str, str | int | dict[str, int]]]] = []
        # Parsable format: file:line:column: [severity] message (rule)
        pattern = r"^(.+?):(\d+):(\d+): \[(\w+)\] (.+?) \((.+?)\)$"

        for line in parsable_output.strip().split("\n"):
            if not line:
                continue
            match = re.match(pattern, line)
            if match:
                file_path, line_num, column, severity, message, rule = match.groups()
                issues.append(
                    {
                        "description": f"{message} ({rule})",
                        "check_name": f"yamllint/{rule}",
                        "fingerprint": f"{file_path}:{line_num}:{column}:{rule}",
                        "severity": "major" if severity == "error" else "minor",
                        "location": {
                            "path": file_path,
                            "lines": {"begin": int(line_num)},
                        },
                    }
                )

        return json.dumps(issues, indent=2)

    def run_yamllint(self, output_format: OutputFormat = "standard") -> int:
        """
        Run yamllint on all YAML files.

        Args:
            output_format: Output format ('standard', 'parsable', 'gitlab')

        Returns:
            Exit code (0 = success, non-zero = failures)
        """
        print("=" * 60)
        print("Running YAML Linting")
        print("=" * 60)

        # Check if yamllint is available
        if not self.check_yamllint_available():
            print("Error: yamllint not found or not executable", file=sys.stderr)
            print("Install: pip install yamllint", file=sys.stderr)
            return 1

        # Get version info
        try:
            version_check = subprocess.run(
                ["yamllint", "--version"],
                capture_output=True,
                text=True,
                timeout=VERSION_CHECK_TIMEOUT,
                check=True,
            )
            self.log(f"yamllint version: {version_check.stdout.strip()}")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"Warning: Could not get yamllint version: {e}", file=sys.stderr)

        # Build command
        cmd = self._build_command(output_format)
        self.log(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=LINT_TIMEOUT,
            )

            # Convert to GitLab format if requested
            if output_format == "gitlab":
                gitlab_json = self._convert_to_gitlab_format(result.stdout)
                print(gitlab_json)
            else:
                # Print output
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)

                # Print summary
                print("\n" + "=" * 60)
                if result.returncode == 0:
                    print("✅ YAML linting passed")
                else:
                    print("❌ YAML linting failed")
                print("=" * 60)

            return result.returncode

        except subprocess.TimeoutExpired:
            print(
                f"Error: yamllint timed out after {LINT_TIMEOUT} seconds",
                file=sys.stderr,
            )
            return 1
        except Exception as e:
            print(f"Error running yamllint: {e}", file=sys.stderr)
            return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run YAML linting with yamllint")
    parser.add_argument(
        "--format",
        choices=["standard", "parsable", "gitlab"],
        default="standard",
        help="Output format (default: standard)",
    )
    parser.add_argument(
        "--output",
        help="Output file for GitLab Code Quality JSON (only with --format gitlab)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    linter = YAMLLinter(verbose=args.verbose)
    # Note: yamllint with --format gitlab writes directly to stdout
    # The CI job will redirect this with > in the script
    return linter.run_yamllint(output_format=args.format)  # type: ignore[arg-type]


if __name__ == "__main__":
    sys.exit(main())
