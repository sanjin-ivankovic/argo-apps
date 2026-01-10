#!/usr/bin/env python3
"""
Unit tests for generate-pipeline.py

Tests cover all major functions including change detection,
manifest discovery, job generation, and pipeline creation.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, Protocol, TYPE_CHECKING
from unittest.mock import patch, MagicMock
import pytest  # type: ignore[import-untyped]
import yaml


# Minimal MonkeyPatch protocol for type checking (only methods we use)
class MonkeyPatchProtocol(Protocol):
    """Protocol for pytest's MonkeyPatch fixture."""

    def setenv(self, name: str, value: str, prepend: str | None = None) -> None:
        """Set environment variable."""
        ...


# Type alias for MonkeyPatch - use protocol for type checking, actual type at runtime
if TYPE_CHECKING:
    # During type checking, use the protocol
    MonkeyPatch = MonkeyPatchProtocol
else:
    # At runtime, try to import actual type, fallback to protocol
    try:
        from _pytest.monkeypatch import MonkeyPatch  # type: ignore[import-untyped]
    except ImportError:
        MonkeyPatch = MonkeyPatchProtocol  # type: ignore[misc]

# Import the module to test
sys.path.insert(0, str(Path(__file__).parent))
import generate_pipeline as gp  # type: ignore

# Test constants
TEST_MR_BRANCH = "main"
TEST_COMMIT_SHA = "abc123"
TEST_AFTER_SHA = "def456"
GIT_TIMEOUT = 30
TEST_RUNNER_TAG = "shared"
TEST_K8S_VERSION = "1.34.3"


class TestGetChangedFiles:
    """Tests for get_changed_files function."""

    def test_merge_request_event(self, monkeypatch: MonkeyPatch) -> None:
        """Test change detection for merge request."""
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "merge_request_event")
        monkeypatch.setenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", TEST_MR_BRANCH)

        mock_result = MagicMock()
        mock_result.stdout = (
            "apps/test/kustomization.yaml\ninfrastructure/test/values.yaml"
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            files = gp.get_changed_files()

            assert len(files) == 2
            assert "apps/test/kustomization.yaml" in files
            assert "infrastructure/test/values.yaml" in files

    def test_push_event_with_before_sha(self, monkeypatch: MonkeyPatch) -> None:
        """Test change detection for push with before SHA."""
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")
        monkeypatch.setenv("CI_COMMIT_BEFORE_SHA", TEST_COMMIT_SHA)
        monkeypatch.setenv("CI_COMMIT_SHA", TEST_AFTER_SHA)

        mock_result = MagicMock()
        mock_result.stdout = "apps/app1/deployment.yaml"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            files = gp.get_changed_files()

            assert len(files) == 1
            assert "apps/app1/deployment.yaml" in files

    def test_timeout_handling(self, monkeypatch: MonkeyPatch) -> None:
        """Test handling of git command timeout."""
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")

        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("git", GIT_TIMEOUT)
        ):
            files = gp.get_changed_files()
            assert files == []

    def test_error_handling(self, monkeypatch: MonkeyPatch) -> None:
        """Test handling of git command errors."""
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")

        with patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")
        ):
            files = gp.get_changed_files()
            assert files == []


class TestFindAllManifests:
    """Tests for find_all_manifests function."""

    def test_finds_kustomizations(self, tmp_path: Path) -> None:
        """Test finding all kustomization.yaml files."""
        # Create test directory structure
        apps_dir: Path = tmp_path / "apps" / "app1"
        apps_dir.mkdir(parents=True)
        (apps_dir / "kustomization.yaml").touch()

        infra_dir: Path = tmp_path / "infrastructure" / "component1"
        infra_dir.mkdir(parents=True)
        (infra_dir / "kustomization.yaml").touch()

        # Change to temp directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            manifests = gp.find_all_manifests()

            assert len(manifests) == 2
            assert Path("apps/app1") in manifests
            assert Path("infrastructure/component1") in manifests
        finally:
            os.chdir(original_cwd)

    def test_handles_missing_directories(self, tmp_path: Path) -> None:
        """Test handling when directories don't exist."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            manifests = gp.find_all_manifests()

            assert len(manifests) == 0
        finally:
            os.chdir(original_cwd)


class TestGetAffectedManifests:
    """Tests for get_affected_manifests function."""

    def test_finds_parent_kustomization(self, tmp_path: Path) -> None:
        """Test finding parent kustomization for changed file."""
        # Create structure
        app_dir: Path = tmp_path / "apps" / "myapp"
        app_dir.mkdir(parents=True)
        (app_dir / "kustomization.yaml").touch()
        (app_dir / "deployment.yaml").touch()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            changed_files = ["apps/myapp/deployment.yaml"]
            affected = gp.get_affected_manifests(changed_files)

            assert len(affected) == 1
            assert Path("apps/myapp") in affected
            assert affected[Path("apps/myapp")]["has_kustomization"] is True
        finally:
            os.chdir(original_cwd)

    def test_handles_file_without_kustomization(self, tmp_path: Path) -> None:
        """Test handling files without parent kustomization."""
        # Create file without kustomization
        app_dir: Path = tmp_path / "apps" / "standalone"
        app_dir.mkdir(parents=True)
        (app_dir / "manifest.yaml").touch()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            changed_files = ["apps/standalone/manifest.yaml"]
            affected = gp.get_affected_manifests(changed_files)

            assert len(affected) == 1
            assert Path("apps/standalone") in affected
            assert affected[Path("apps/standalone")]["has_kustomization"] is False
        finally:
            os.chdir(original_cwd)

    def test_ignores_non_relevant_paths(self) -> None:
        """Test that non-relevant paths are ignored."""
        changed_files = [
            "README.md",
            "docs/guide.md",
            ".gitlab-ci.yml",
        ]
        affected = gp.get_affected_manifests(changed_files)

        assert len(affected) == 0

    def test_tracks_source_files(self, tmp_path: Path) -> None:
        """Test that source files are tracked."""
        app_dir: Path = tmp_path / "apps" / "myapp"
        app_dir.mkdir(parents=True)
        (app_dir / "kustomization.yaml").touch()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            changed_files = [
                "apps/myapp/deployment.yaml",
                "apps/myapp/service.yaml",
            ]
            affected = gp.get_affected_manifests(changed_files)

            assert len(affected[Path("apps/myapp")]["files"]) == 2
        finally:
            os.chdir(original_cwd)


class TestGenerateValidationJob:
    """Tests for generate_validation_job function."""

    def test_kustomize_job_generation(self) -> None:
        """Test generation of kustomize validation job."""
        manifest_dir = Path("apps/myapp")
        job = gp.generate_validation_job(manifest_dir, "validate-kustomize")

        job_name = f"validate-kustomize:apps-myapp"
        assert job_name in job

        job_config = job[job_name]
        assert job_config["stage"] == "validate"
        assert job_config["variables"]["COMPONENT_TYPE"] == "app"
        assert "kustomize build" in " ".join(job_config["script"])
        assert "kubeconform" in " ".join(job_config["script"])

    def test_raw_manifest_job_generation(self) -> None:
        """Test generation of raw manifest validation job."""
        manifest_dir = Path("apps/standalone")
        source_files = ["apps/standalone/deployment.yaml"]
        job = gp.generate_validation_job(manifest_dir, "validate-raw", source_files)

        job_name = f"validate-raw:apps-standalone"
        assert job_name in job

        job_config = job[job_name]
        assert "kubeconform" in " ".join(job_config["script"])
        assert "apps/standalone/deployment.yaml" in " ".join(job_config["script"])

    def test_infrastructure_component_type(self) -> None:
        """Test component type detection for infrastructure."""
        manifest_dir = Path("infrastructure/monitoring")
        job = gp.generate_validation_job(manifest_dir, "validate-kustomize")

        job_config = list(job.values())[0]
        assert job_config["variables"]["COMPONENT_TYPE"] == "infrastructure"

    def test_argocd_component_type(self) -> None:
        """Test component type detection for argocd."""
        manifest_dir = Path("argocd/apps")
        job = gp.generate_validation_job(manifest_dir, "validate-kustomize")

        job_config = list(job.values())[0]
        assert job_config["variables"]["COMPONENT_TYPE"] == "argocd"


class TestGenerateChildPipeline:
    """Tests for generate_child_pipeline function."""

    def test_empty_manifests(self) -> None:
        """Test pipeline generation with no manifests."""
        manifests: Dict[Path, Dict[str, Any]] = {}
        pipeline = gp.generate_child_pipeline(manifests)

        assert "variables" in pipeline
        assert "stages" in pipeline
        assert "no-changes" in pipeline
        assert pipeline["no-changes"]["stage"] == "validate"

    def test_single_manifest(self) -> None:
        """Test pipeline generation with one manifest."""
        manifests: Dict[Path, Dict[str, Any]] = {
            Path("apps/myapp"): {
                "has_kustomization": True,
                "files": set(),
            }
        }
        pipeline = gp.generate_child_pipeline(manifests)

        assert "validate-kustomize:apps-myapp" in pipeline
        assert "no-changes" not in pipeline

    def test_multiple_manifests(self) -> None:
        """Test pipeline generation with multiple manifests."""
        manifests: Dict[Path, Dict[str, Any]] = {
            Path("apps/app1"): {"has_kustomization": True, "files": set()},
            Path("apps/app2"): {"has_kustomization": True, "files": set()},
            Path("infrastructure/monitoring"): {
                "has_kustomization": True,
                "files": set(),
            },
        }
        pipeline = gp.generate_child_pipeline(manifests)

        assert "validate-kustomize:apps-app1" in pipeline
        assert "validate-kustomize:apps-app2" in pipeline
        assert "validate-kustomize:infrastructure-monitoring" in pipeline

    def test_mixed_kustomize_and_raw(self) -> None:
        """Test pipeline with both kustomize and raw manifests."""
        manifests: Dict[Path, Dict[str, Any]] = {
            Path("apps/with-kustomize"): {
                "has_kustomization": True,
                "files": set(),
            },
            Path("apps/without-kustomize"): {
                "has_kustomization": False,
                "files": {"apps/without-kustomize/manifest.yaml"},
            },
        }
        pipeline = gp.generate_child_pipeline(manifests)

        assert "validate-kustomize:apps-with-kustomize" in pipeline
        assert "validate-raw:apps-without-kustomize" in pipeline

    def test_pipeline_structure(self) -> None:
        """Test that pipeline has required structure."""
        manifests: Dict[Path, Dict[str, Any]] = {
            Path("apps/myapp"): {"has_kustomization": True, "files": set()},
        }
        pipeline = gp.generate_child_pipeline(manifests)

        assert "variables" in pipeline
        assert "CI_IMAGE" in pipeline["variables"]
        assert "KUBERNETES_VERSION" in pipeline["variables"]
        assert "stages" in pipeline
        assert "validate" in pipeline["stages"]


class TestMain:
    """Tests for main function."""

    def test_generates_valid_yaml(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that main generates valid YAML output."""
        # Create test structure
        app_dir: Path = tmp_path / "apps" / "testapp"
        app_dir.mkdir(parents=True)
        (app_dir / "kustomization.yaml").touch()

        output_file: Path = tmp_path / "child-pipeline.yml"

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Mock get_changed_files to return our test file
            with patch(
                "generate_pipeline.get_changed_files",
                return_value=["apps/testapp/kustomization.yaml"],
            ):
                gp.main()

            # Verify output file exists and is valid YAML
            assert output_file.exists()

            with open(output_file) as f:
                pipeline = yaml.safe_load(f)

            assert isinstance(pipeline, dict)
            assert "variables" in pipeline
            assert "stages" in pipeline
        finally:
            os.chdir(original_cwd)

    def test_fallback_job_on_empty_pipeline(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that fallback job is added for empty pipeline."""
        output_file: Path = tmp_path / "child-pipeline.yml"

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            with patch("generate_pipeline.get_changed_files", return_value=[]):
                with patch("generate_pipeline.find_all_manifests", return_value={}):
                    gp.main()

            with open(output_file) as f:
                pipeline = yaml.safe_load(f)

            # Should have workflow, variables, stages, and at least one job
            assert len(pipeline) > 3
        finally:
            os.chdir(original_cwd)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_constants_match_expectations(self) -> None:
        """Test that constants in generate_pipeline.py match expectations."""
        assert gp.SCAN_DIRECTORIES == ["apps", "infrastructure", "argocd"]
        assert gp.GIT_TIMEOUT == GIT_TIMEOUT
        assert gp.DEFAULT_RUNNER_TAG == TEST_RUNNER_TAG
        assert len(gp.KUBECONFORM_SCHEMA_LOCATIONS) > 0
        # Verify schema locations string contains valid URL
        assert "https://" in gp.KUBECONFORM_SCHEMA_LOCATIONS
        assert "datreeio/CRDs-catalog" in gp.KUBECONFORM_SCHEMA_LOCATIONS

    def test_nested_kustomizations(self, tmp_path: Path) -> None:
        """Test handling of nested kustomization directories."""
        # Create nested structure
        parent: Path = tmp_path / "apps" / "parent"
        parent.mkdir(parents=True)
        (parent / "kustomization.yaml").touch()

        child: Path = parent / "child"
        child.mkdir()
        (child / "kustomization.yaml").touch()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Change in child should find child kustomization
            changed_files = ["apps/parent/child/deployment.yaml"]
            affected = gp.get_affected_manifests(changed_files)

            assert Path("apps/parent/child") in affected
        finally:
            os.chdir(original_cwd)

    def test_empty_file_list(self) -> None:
        """Test handling of empty changed files list."""
        affected = gp.get_affected_manifests([])
        assert len(affected) == 0

    def test_special_characters_in_path(self, tmp_path: Path) -> None:
        """Test handling of special characters in paths."""
        app_dir: Path = tmp_path / "apps" / "my-app_v2"
        app_dir.mkdir(parents=True)
        (app_dir / "kustomization.yaml").touch()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            changed_files = ["apps/my-app_v2/kustomization.yaml"]
            affected = gp.get_affected_manifests(changed_files)

            assert len(affected) == 1

            # Generate job and verify name is sanitized
            job = gp.generate_validation_job(
                Path("apps/my-app_v2"), "validate-kustomize"
            )
            job_name = list(job.keys())[0]
            assert "my-app_v2" in job_name
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])  # type: ignore
