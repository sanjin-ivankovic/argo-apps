"""Tests for detect_apps.py against a throwaway git repo."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import detect_apps

ENV_VARS = ("CI_MERGE_REQUEST_DIFF_BASE_SHA", "CI_COMMIT_BEFORE_SHA", "CI_COMMIT_SHA")


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(repo: Path, path: str, msg: str) -> str:
    f = repo / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(msg + "\n")
    run("git", "add", path, cwd=repo)
    run("git", "commit", "-q", "-m", msg, cwd=repo)
    return run("git", "rev-parse", "HEAD", cwd=repo)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    run("git", "init", "-q", "-b", "main", cwd=tmp_path)
    run("git", "config", "user.email", "t@example.invalid", cwd=tmp_path)
    run("git", "config", "user.name", "t", cwd=tmp_path)
    for app in ("apps/user/memos", "apps/user/wiki", "apps/infra/traefik"):
        commit(tmp_path, f"{app}/kustomization.yaml", f"init {app}")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_mr_range_covers_every_commit(repo, monkeypatch):
    base = run("git", "rev-parse", "HEAD", cwd=repo)
    commit(repo, "apps/user/memos/values.yaml", "first")
    head = commit(repo, "apps/user/wiki/values.yaml", "second")
    monkeypatch.setenv("CI_MERGE_REQUEST_DIFF_BASE_SHA", base)
    monkeypatch.setenv("CI_COMMIT_BEFORE_SHA", detect_apps.ZERO_SHA)
    monkeypatch.setenv("CI_COMMIT_SHA", head)
    assert detect_apps.affected_apps(detect_apps.changed_files()) == [
        "apps/user/memos",
        "apps/user/wiki",
    ]


def test_push_range_uses_before_sha(repo, monkeypatch):
    before = run("git", "rev-parse", "HEAD", cwd=repo)
    commit(repo, "apps/infra/traefik/values.yaml", "one")
    head = commit(repo, "apps/user/memos/values.yaml", "two")
    monkeypatch.setenv("CI_COMMIT_BEFORE_SHA", before)
    monkeypatch.setenv("CI_COMMIT_SHA", head)
    assert detect_apps.affected_apps(detect_apps.changed_files()) == [
        "apps/infra/traefik",
        "apps/user/memos",
    ]


def test_zero_before_sha_falls_back_to_head_parent(repo, monkeypatch):
    commit(repo, "apps/user/wiki/values.yaml", "only")
    monkeypatch.setenv("CI_COMMIT_BEFORE_SHA", detect_apps.ZERO_SHA)
    assert detect_apps.affected_apps(detect_apps.changed_files()) == ["apps/user/wiki"]


def test_unknown_base_lists_everything(repo, monkeypatch):
    monkeypatch.setenv("CI_MERGE_REQUEST_DIFF_BASE_SHA", "1" * 40)
    assert detect_apps.changed_files() == ["EVERYTHING"]


def test_single_commit_repo_lists_everything(tmp_path, monkeypatch):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    run("git", "init", "-q", "-b", "main", cwd=tmp_path)
    run("git", "config", "user.email", "t@example.invalid", cwd=tmp_path)
    run("git", "config", "user.name", "t", cwd=tmp_path)
    commit(tmp_path, "apps/user/memos/kustomization.yaml", "init")
    monkeypatch.chdir(tmp_path)
    assert detect_apps.changed_files() == ["EVERYTHING"]


def test_affected_apps_ignores_non_app_paths(repo):
    files = [
        "README.md",
        "apps/README.md",
        "apps/user/memos/values.yaml",
        "apps/user/gone/values.yaml",
        "argocd/apps-set.yaml",
    ]
    assert detect_apps.affected_apps(files) == ["apps/user/memos"]


def test_all_app_dirs(repo):
    assert detect_apps.all_app_dirs() == [
        "apps/infra/traefik",
        "apps/user/memos",
        "apps/user/wiki",
    ]


def test_main_writes_output(repo, monkeypatch, capsys):
    commit(repo, "apps/user/memos/values.yaml", "change")
    out = repo / "changed.json"
    monkeypatch.setattr(sys, "argv", ["detect_apps.py", "--output", str(out)])
    assert detect_apps.main() == 0
    assert json.loads(out.read_text()) == ["apps/user/memos"]
    assert json.loads(capsys.readouterr().out) == ["apps/user/memos"]


def test_main_everything(repo, monkeypatch, capsys):
    monkeypatch.setenv("CI_MERGE_REQUEST_DIFF_BASE_SHA", "1" * 40)
    monkeypatch.setattr(sys, "argv", ["detect_apps.py"])
    assert detect_apps.main() == 0
    assert len(json.loads(capsys.readouterr().out)) == 3
