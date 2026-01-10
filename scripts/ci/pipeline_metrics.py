#!/usr/bin/env python3
"""
Pipeline Metrics Tracking Script

Fetches pipeline data from GitLab API and generates performance reports.
Tracks job durations, success rates, and trends over time.

Usage:
    python3 pipeline_metrics.py --project-id 123 --token $GITLAB_TOKEN
    python3 pipeline_metrics.py --days 30 --format markdown
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Literal

# Constants
DEFAULT_PER_PAGE = 100
DEFAULT_GITLAB_URL = "https://gitlab.com"
TOP_JOBS_LIMIT = 15
RECENT_PIPELINES_LIMIT = 10
REQUESTS_TIMEOUT = 30

# Type alias
ReportFormat = Literal["json", "markdown"]

try:
    import requests  # type: ignore[import-not-found]
except ImportError:
    print("ERROR: requests library required. Install with: pip install requests")
    sys.exit(1)


@dataclass
class JobMetrics:
    """Metrics for a single job."""

    name: str
    duration_seconds: float
    status: str
    stage: str


@dataclass
class PipelineMetrics:
    """Metrics for a single pipeline."""

    id: int
    created_at: datetime
    duration_seconds: float
    status: str
    jobs: List[JobMetrics]


class GitLabMetricsCollector:
    """Collects pipeline metrics from GitLab API."""

    def __init__(
        self,
        project_id: str,
        token: str,
        gitlab_url: str = "https://gitlab.com",
        verbose: bool = False,
    ):
        self.project_id = project_id
        self.token = token
        self.gitlab_url = gitlab_url.rstrip("/")
        self.api_base = f"{self.gitlab_url}/api/v4"

        # Setup logging
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
        self.logger = logging.getLogger(__name__)

        # Setup session
        self.session = requests.Session()
        # Use Bearer authentication which supports both PATs and CI Job Tokens
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def fetch_pipelines(self, days: int = 30) -> List[Dict[str, Any]]:
        """Fetch pipelines from the last N days."""
        since = datetime.now() - timedelta(days=days)

        url = f"{self.api_base}/projects/{self.project_id}/pipelines"
        params: Dict[str, Any] = {
            "updated_after": since.isoformat(),
            "per_page": DEFAULT_PER_PAGE,
            "order_by": "updated_at",
            "sort": "desc",
        }

        self.logger.info(f"Fetching pipelines from last {days} days...")

        pipelines: List[Dict[str, Any]] = []
        page = 1

        while True:
            params["page"] = page
            response = self.session.get(url, params=params, timeout=REQUESTS_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            if not data:
                break

            pipelines.extend(data)
            self.logger.debug(f"Fetched page {page}: {len(data)} pipelines")

            # Check if there are more pages
            if (
                "x-next-page" not in response.headers
                or not response.headers["x-next-page"]
            ):
                break

            page += 1

        self.logger.info(f"Fetched {len(pipelines)} pipelines")
        return pipelines

    def fetch_pipeline_jobs(self, pipeline_id: int) -> List[Dict[str, Any]]:
        """Fetch jobs for a specific pipeline."""
        url = f"{self.api_base}/projects/{self.project_id}/pipelines/{pipeline_id}/jobs"

        response = self.session.get(url, timeout=REQUESTS_TIMEOUT)
        response.raise_for_status()

        return response.json()

    def fetch_pipeline_details(self, pipeline_id: int) -> Dict[str, Any]:
        """Fetch details for a specific pipeline (includes duration)."""
        url = f"{self.api_base}/projects/{self.project_id}/pipelines/{pipeline_id}"
        response = self.session.get(url, timeout=REQUESTS_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def collect_metrics(self, days: int = 30) -> List[PipelineMetrics]:
        """Collect metrics for all pipelines."""
        pipelines_data = self.fetch_pipelines(days)
        metrics: List[PipelineMetrics] = []

        for pipeline_basic in pipelines_data:
            pipeline_id: int = pipeline_basic["id"]

            try:
                # Need to fetch details to get duration
                pipeline: Dict[str, Any] = self.fetch_pipeline_details(pipeline_id)

                # Skip if no duration (still running or failed early)
                if not pipeline.get("duration"):
                    continue

                jobs_data: List[Dict[str, Any]] = self.fetch_pipeline_jobs(pipeline_id)

                jobs: List[JobMetrics] = [
                    JobMetrics(
                        name=str(job["name"]),
                        duration_seconds=float(job.get("duration", 0) or 0),
                        status=str(job["status"]),
                        stage=str(job["stage"]),
                    )
                    for job in jobs_data
                ]

                metrics.append(
                    PipelineMetrics(
                        id=pipeline_id,
                        created_at=datetime.fromisoformat(
                            str(pipeline["created_at"]).replace("Z", "+00:00")
                        ),
                        duration_seconds=float(pipeline["duration"]),
                        status=str(pipeline["status"]),
                        jobs=jobs,
                    )
                )

            except Exception as e:
                self.logger.warning(
                    f"Failed to fetch jobs for pipeline {pipeline_id}: {e}"
                )

        self.logger.info(f"Collected metrics for {len(metrics)} pipelines")
        return metrics


class MetricsAnalyzer:
    """Analyzes pipeline metrics and generates reports."""

    def __init__(self, metrics: List[PipelineMetrics]):
        self.metrics = metrics
        self._duration_stats_cache: Dict[str, float] | None = None
        self._job_stats_cache: Dict[str, Dict[str, float]] | None = None

    def calculate_success_rate(self) -> float:
        """Calculate overall success rate."""
        if not self.metrics:
            return 0.0

        successful = sum(1 for m in self.metrics if m.status == "success")
        return (successful / len(self.metrics)) * 100

    def calculate_duration_stats(self) -> Dict[str, float]:
        """Calculate duration statistics."""
        if self._duration_stats_cache is not None:
            return self._duration_stats_cache

        durations = [m.duration_seconds for m in self.metrics if m.duration_seconds > 0]

        if not durations:
            return {"mean": 0, "median": 0, "min": 0, "max": 0}

        self._duration_stats_cache = {
            "mean": mean(durations),
            "median": median(durations),
            "min": min(durations),
            "max": max(durations),
        }
        return self._duration_stats_cache

    def calculate_job_stats(self) -> Dict[str, Dict[str, float]]:
        """Calculate statistics per job."""
        job_durations: Dict[str, List[float]] = defaultdict(list)

        for pipeline in self.metrics:
            for job in pipeline.jobs:
                if job.duration_seconds > 0:
                    job_durations[job.name].append(job.duration_seconds)

        stats: Dict[str, Dict[str, float]] = {}
        for job_name, durations in job_durations.items():
            stats[job_name] = {
                "mean": mean(durations),
                "median": median(durations),
                "min": min(durations),
                "max": max(durations),
                "count": len(durations),
            }

        self._job_stats_cache = stats
        return stats

    def generate_json_report(self) -> str:
        """Generate JSON report."""
        report: Dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "total_pipelines": len(self.metrics),
            "success_rate": self.calculate_success_rate(),
            "duration_stats": self.calculate_duration_stats(),
            "job_stats": self.calculate_job_stats(),
            "recent_pipelines": [
                {
                    "id": m.id,
                    "created_at": m.created_at.isoformat(),
                    "duration_seconds": m.duration_seconds,
                    "status": m.status,
                }
                for m in sorted(self.metrics, key=lambda x: x.created_at, reverse=True)[
                    :RECENT_PIPELINES_LIMIT
                ]
            ],
        }

        return json.dumps(report, indent=2)

    def generate_markdown_report(self) -> str:
        """Generate Markdown report."""
        success_rate = self.calculate_success_rate()
        duration_stats = self.calculate_duration_stats()
        job_stats = self.calculate_job_stats()

        report = f"""# Pipeline Metrics Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overview

- **Total Pipelines**: {len(self.metrics)}
- **Success Rate**: {success_rate:.1f}%
- **Average Duration**: {duration_stats['mean'] / 60:.1f} minutes
- **Median Duration**: {duration_stats['median'] / 60:.1f} minutes

## Duration Statistics

| Metric | Value |
|--------|-------|
| Mean | {duration_stats['mean'] / 60:.1f} min |
| Median | {duration_stats['median'] / 60:.1f} min |
| Min | {duration_stats['min'] / 60:.1f} min |
| Max | {duration_stats['max'] / 60:.1f} min |

## Job Performance

| Job Name | Avg Duration | Median | Min | Max | Runs |
|----------|--------------|--------|-----|-----|------|
"""

        # Sort jobs by average duration (slowest first)
        sorted_jobs = sorted(
            job_stats.items(), key=lambda x: x[1]["mean"], reverse=True
        )

        for job_name, stats in sorted_jobs[:TOP_JOBS_LIMIT]:  # Top slowest jobs
            report += f"| {job_name} | {stats['mean']:.1f}s | {stats['median']:.1f}s | {stats['min']:.1f}s | {stats['max']:.1f}s | {stats['count']} |\n"

        report += "\n## Recent Pipelines\n\n"
        report += "| ID | Date | Duration | Status |\n"
        report += "|----|------|----------|--------|\n"

        for pipeline in sorted(self.metrics, key=lambda x: x.created_at, reverse=True)[
            :RECENT_PIPELINES_LIMIT
        ]:
            status_emoji = "✅" if pipeline.status == "success" else "❌"
            report += f"| {pipeline.id} | {pipeline.created_at.strftime('%Y-%m-%d %H:%M')} | {pipeline.duration_seconds / 60:.1f} min | {status_emoji} {pipeline.status} |\n"

        return report


def main() -> int:
    # Use CI_SERVER_URL if available (running in GitLab CI), otherwise fall back to public GitLab
    default_url = os.getenv("CI_SERVER_URL", DEFAULT_GITLAB_URL)

    parser = argparse.ArgumentParser(
        description="Collect and analyze GitLab pipeline metrics"
    )
    parser.add_argument("--project-id", required=True, help="GitLab project ID")
    parser.add_argument("--token", required=True, help="GitLab API token")
    parser.add_argument(
        "--gitlab-url",
        default=default_url,
        help=f"GitLab instance URL (default: $CI_SERVER_URL or {DEFAULT_GITLAB_URL})",
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Number of days to analyze (default: 30)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument("--output", type=Path, help="Output file (default: stdout)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    try:
        # Collect metrics
        collector = GitLabMetricsCollector(
            project_id=args.project_id,
            token=args.token,
            gitlab_url=args.gitlab_url,
            verbose=args.verbose,
        )

        metrics = collector.collect_metrics(days=args.days)

        if not metrics:
            print("No pipeline metrics found", file=sys.stderr)
            return 1

        # Analyze and generate report
        analyzer = MetricsAnalyzer(metrics)

        if args.format == "json":
            report = analyzer.generate_json_report()
        else:
            report = analyzer.generate_markdown_report()

        # Output
        if args.output:
            args.output.write_text(report)
            print(f"Report written to: {args.output}")
        else:
            print(report)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
