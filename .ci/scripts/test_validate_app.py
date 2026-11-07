"""Tests for the vendored-chart pin check in validate_app.py."""

from pathlib import Path

import yaml

from validate_app import check_vendored


def make_app(tmp_path: Path, pin: str, copies: dict[str, str]) -> Path:
    app = tmp_path / "apps/data/postgresql"
    app.mkdir(parents=True)
    (app / "kustomization.yaml").write_text(
        yaml.safe_dump({"helmCharts": [{"name": "postgresql", "version": pin}]})
    )
    for dirname, version in copies.items():
        chart = app / "charts" / dirname / "postgresql"
        chart.mkdir(parents=True)
        (chart / "Chart.yaml").write_text(yaml.safe_dump({"version": version}))
    return app


def test_matching_copy_passes(tmp_path):
    app = make_app(tmp_path, "1.1.0", {"postgresql-1.1.0": "1.1.0"})
    assert check_vendored(app) is None


def test_missing_copy_fails(tmp_path):
    app = make_app(tmp_path, "1.2.0", {"postgresql-1.1.0": "1.1.0"})
    assert "missing" in check_vendored(app)


def test_wrong_version_inside_copy_fails(tmp_path):
    app = make_app(tmp_path, "1.1.0", {"postgresql-1.1.0": "1.0.9"})
    assert "kustomization pins 1.1.0" in check_vendored(app)


def test_stale_copy_fails(tmp_path):
    app = make_app(
        tmp_path,
        "1.1.0",
        {"postgresql-1.1.0": "1.1.0", "postgresql-1.0.0": "1.0.0"},
    )
    assert "stale vendored copies" in check_vendored(app)
