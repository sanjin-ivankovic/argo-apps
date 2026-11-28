"""Tests for the vendored-chart pin check in validate_app.py."""

from pathlib import Path

import yaml

from validate_app import REQUESTS_EXEMPT, check_vendored, missing_requests


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


def workload(kind: str, containers: list[dict], name: str = "app") -> str:
    pod = {"containers": containers}
    if kind == "Pod":
        spec = pod
    elif kind == "CronJob":
        spec = {"jobTemplate": {"spec": {"template": {"spec": pod}}}}
    else:
        spec = {"template": {"spec": pod}}
    return yaml.safe_dump({"kind": kind, "metadata": {"name": name}, "spec": spec})


REQUESTED = {"name": "main", "resources": {"requests": {"cpu": "10m", "memory": "32Mi"}}}


def test_requested_containers_pass():
    docs = "---\n".join(workload(k, [REQUESTED]) for k in ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob", "Pod"))
    assert missing_requests(docs) == []


def test_container_without_requests_is_reported():
    docs = workload("Deployment", [REQUESTED, {"name": "sidecar"}])
    assert missing_requests(docs) == ["Deployment/app/sidecar"]


def test_cpu_only_request_is_reported():
    docs = workload("CronJob", [{"name": "main", "resources": {"requests": {"cpu": "10m"}}}])
    assert missing_requests(docs) == ["CronJob/app/main"]


def test_init_containers_and_other_kinds_are_ignored():
    deploy = yaml.safe_load(workload("Deployment", [REQUESTED]))
    deploy["spec"]["template"]["spec"]["initContainers"] = [{"name": "init"}]
    docs = yaml.safe_dump(deploy) + "---\n" + yaml.safe_dump({"kind": "ConfigMap", "metadata": {"name": "x"}})
    assert missing_requests(docs) == []


def test_bare_equals_sign_does_not_break_parsing():
    docs = "kind: ConfigMap\nmetadata: {name: x}\ndata:\n  ops: [=, '!=']\n---\n" + workload("Deployment", [{"name": "main"}])
    assert missing_requests(docs) == ["Deployment/app/main"]


def test_exempt_container_passes(monkeypatch):
    monkeypatch.setitem(REQUESTS_EXEMPT, "Deployment/app/main", "test")
    assert missing_requests(workload("Deployment", [{"name": "main"}])) == []
