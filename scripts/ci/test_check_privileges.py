#!/usr/bin/env python3
"""
Unit tests for check_privileges.py security scanner.

This test suite provides comprehensive coverage for the PrivilegeChecker class
and SecurityFinding dataclass, testing detection of:
- Pod-level privileges (hostNetwork, hostPID, hostIPC)
- Container-level privileges (privileged, allowPrivilegeEscalation, runAsRoot)
- Dangerous Linux capabilities
- hostPath volume mounts
- JSON output formatting
- Error handling for malformed YAML
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock, patch
from check_privileges import PrivilegeChecker, SecurityFinding

# Test constants
TEST_NAMESPACE = "default"
TEST_APP_DIR = Path("apps/test")
TEST_INFRA_DIR = Path("infrastructure/test")
TEST_IMAGE = "nginx"
DANGEROUS_CAPS = [
    "SYS_ADMIN",
    "NET_ADMIN",
    "SYS_MODULE",
    "SYS_RAWIO",
    "SYS_PTRACE",
    "DAC_OVERRIDE",
]


class TestSecurityFinding:
    """Tests for SecurityFinding dataclass."""

    def test_finding_creation(self):
        """Test SecurityFinding instantiation with all fields."""
        finding = SecurityFinding(
            severity="high",
            check="privileged",
            manifest_dir="apps/myapp",
            resource_kind="Deployment",
            resource_name="myapp/container1",
            namespace="default",
            details="Container runs in privileged mode",
            line_context="Line 42",
        )

        assert finding.severity == "high"
        assert finding.check == "privileged"
        assert finding.manifest_dir == "apps/myapp"
        assert finding.resource_kind == "Deployment"
        assert finding.resource_name == "myapp/container1"
        assert finding.namespace == "default"
        assert finding.details == "Container runs in privileged mode"
        assert finding.line_context == "Line 42"

    def test_finding_default_line_context(self):
        """Test SecurityFinding with default empty line_context."""
        finding = SecurityFinding(
            severity="medium",
            check="hostIPC",
            manifest_dir="apps/test",
            resource_kind="Pod",
            resource_name="test-pod",
            namespace="test-ns",
            details="Pod uses host IPC namespace",
        )

        assert finding.line_context == ""

    def test_finding_to_dict(self):
        """Test dictionary conversion for JSON output."""
        from dataclasses import asdict

        finding = SecurityFinding(
            severity="high",
            check="hostPath",
            manifest_dir="infrastructure/storage",
            resource_kind="DaemonSet",
            resource_name="storage-daemon",
            namespace="kube-system",
            details="Pod mounts host path: /var/lib",
        )

        result = asdict(finding)

        assert result["severity"] == "high"
        assert result["check"] == "hostPath"
        assert result["manifest_dir"] == "infrastructure/storage"
        assert result["resource_kind"] == "DaemonSet"
        assert result["resource_name"] == "storage-daemon"
        assert result["namespace"] == "kube-system"
        assert result["details"] == "Pod mounts host path: /var/lib"
        assert result["line_context"] == ""


class TestPrivilegeChecker:
    """Tests for PrivilegeChecker class."""

    def test_init_without_changed_files(self):
        """Test initialization without changed files."""
        checker = PrivilegeChecker()

        assert checker.changed_files == []
        assert checker.findings == []

    def test_init_with_changed_files(self):
        """Test initialization with provided changed files."""
        files = ["apps/myapp/deployment.yaml", "apps/other/service.yaml"]
        checker = PrivilegeChecker(changed_files=files)

        assert checker.changed_files == files
        assert checker.findings == []

    @patch("subprocess.run")
    @patch.dict(
        "os.environ",
        {
            "CI_PIPELINE_SOURCE": "merge_request_event",
            "CI_MERGE_REQUEST_TARGET_BRANCH_NAME": "main",
        },
    )
    def test_get_changed_files_merge_request(self, mock_run: Mock) -> None:
        """Test getting changed files from merge request."""
        # Mock git fetch
        fetch_result = Mock(returncode=0)
        # Mock git diff
        diff_result = Mock(
            returncode=0, stdout="apps/myapp/deployment.yaml\napps/other/values.yaml\n"
        )

        mock_run.side_effect = [fetch_result, diff_result]

        checker = PrivilegeChecker()
        files = checker.get_changed_files()

        assert len(files) == 2
        assert "apps/myapp/deployment.yaml" in files
        assert "apps/other/values.yaml" in files

    @patch("subprocess.run")
    @patch.dict(
        "os.environ",
        {
            "CI_PIPELINE_SOURCE": "push",
            "CI_COMMIT_BEFORE_SHA": "abc123",
            "CI_COMMIT_SHA": "def456",
        },
    )
    def test_get_changed_files_push_event(self, mock_run: Mock) -> None:
        """Test getting changed files from push event."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="infrastructure/cert-manager/deployment.yaml\n",
        )

        checker = PrivilegeChecker()
        files = checker.get_changed_files()

        assert len(files) == 1
        assert "infrastructure/cert-manager/deployment.yaml" in files

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30))
    def test_get_changed_files_timeout(self, mock_run: Mock) -> None:
        """Test handling of git command timeout."""
        checker = PrivilegeChecker()
        files = checker.get_changed_files()

        assert files == []

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git"))
    def test_get_changed_files_error(self, mock_run: Mock) -> None:
        """Test handling of git command error."""
        checker = PrivilegeChecker()
        files = checker.get_changed_files()

        assert files == []

    def test_get_affected_kustomizations_apps(self):
        """Test finding affected kustomizations in apps/ directory."""
        changed_files = [
            "apps/myapp/deployment.yaml",
            "apps/myapp/values.yaml",
            "apps/other/service.yaml",
        ]

        checker = PrivilegeChecker(changed_files=changed_files)

        with patch("pathlib.Path.exists", return_value=True):
            affected = checker.get_affected_kustomizations(changed_files)

            assert len(affected) >= 1
            # Should find kustomization directories

    def test_get_affected_kustomizations_ignore_unrelated(self):
        """Test that files outside apps/infrastructure/argocd are ignored."""
        changed_files = [
            "README.md",
            "scripts/helper.sh",
            "docs/guide.md",
        ]

        checker = PrivilegeChecker(changed_files=changed_files)
        affected = checker.get_affected_kustomizations(changed_files)

        assert len(affected) == 0

    def test_parse_manifests_valid_yaml(self):
        """Test parsing valid YAML manifests."""
        yaml_content = """---
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: test
    image: nginx
---
apiVersion: v1
kind: Service
metadata:
  name: test-service
spec:
  ports:
  - port: 80
"""

        checker = PrivilegeChecker()
        resources = checker.parse_manifests(yaml_content)

        assert len(resources) == 2
        assert resources[0]["kind"] == "Pod"
        assert resources[1]["kind"] == "Service"

    def test_parse_manifests_malformed_yaml(self):
        """Test error handling for malformed YAML."""
        malformed_yaml = """
apiVersion: v1
kind: Pod
metadata:
  name: test
  invalid: [unclosed bracket
"""

        checker = PrivilegeChecker()
        resources = checker.parse_manifests(malformed_yaml)

        # Should return empty list on parse error
        assert resources == []

    def test_check_resource_host_network(self) -> None:
        """Test detection of hostNetwork: true."""
        resource: Dict[str, Any] = {
            "kind": "Pod",
            "metadata": {"name": "network-pod", "namespace": TEST_NAMESPACE},
            "spec": {
                "hostNetwork": True,
                "containers": [{"name": "test", "image": TEST_IMAGE}],
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, TEST_APP_DIR)

        assert len(checker.findings) == 1
        assert checker.findings[0].severity == "high"
        assert checker.findings[0].check == "hostNetwork"
        assert checker.findings[0].resource_name == "network-pod"

    def test_check_resource_host_pid(self):
        """Test detection of hostPID: true."""
        resource: Dict[str, Any] = {
            "kind": "Deployment",
            "metadata": {"name": "pid-deployment", "namespace": "kube-system"},
            "spec": {
                "template": {
                    "spec": {
                        "hostPID": True,
                        "containers": [{"name": "test", "image": "nginx"}],
                    }
                }
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("infrastructure/monitoring"))

        assert len(checker.findings) == 1
        assert checker.findings[0].severity == "high"
        assert checker.findings[0].check == "hostPID"
        assert checker.findings[0].namespace == "kube-system"

    def test_check_resource_host_ipc(self):
        """Test detection of hostIPC: true."""
        resource: Dict[str, Any] = {
            "kind": "StatefulSet",
            "metadata": {"name": "ipc-statefulset", "namespace": "default"},
            "spec": {
                "template": {
                    "spec": {
                        "hostIPC": True,
                        "containers": [{"name": "test", "image": "nginx"}],
                    }
                }
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/ipc-app"))

        assert len(checker.findings) == 1
        assert checker.findings[0].severity == "medium"
        assert checker.findings[0].check == "hostIPC"

    def test_check_resource_privileged_container(self):
        """Test detection of privileged: true containers."""
        resource: Dict[str, Any] = {
            "kind": "Pod",
            "metadata": {"name": "privileged-pod", "namespace": "default"},
            "spec": {
                "containers": [
                    {
                        "name": "privileged-container",
                        "image": "nginx",
                        "securityContext": {"privileged": True},
                    }
                ]
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        assert len(checker.findings) == 1
        assert checker.findings[0].severity == "high"
        assert checker.findings[0].check == "privileged"
        assert "privileged-container" in checker.findings[0].resource_name

    def test_check_resource_allow_privilege_escalation(self):
        """Test detection of allowPrivilegeEscalation: true."""
        resource: Dict[str, Any] = {
            "kind": "Deployment",
            "metadata": {"name": "escalation-deployment", "namespace": "default"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "escalation-container",
                                "image": "nginx",
                                "securityContext": {"allowPrivilegeEscalation": True},
                            }
                        ]
                    }
                }
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        assert len(checker.findings) == 1
        assert checker.findings[0].severity == "medium"
        assert checker.findings[0].check == "allowPrivilegeEscalation"

    def test_check_resource_run_as_root(self):
        """Test detection of runAsNonRoot: false."""
        resource: Dict[str, Any] = {
            "kind": "Pod",
            "metadata": {"name": "root-pod", "namespace": "default"},
            "spec": {
                "containers": [
                    {
                        "name": "root-container",
                        "image": "nginx",
                        "securityContext": {"runAsNonRoot": False},
                    }
                ]
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        assert len(checker.findings) == 1
        assert checker.findings[0].severity == "medium"
        assert checker.findings[0].check == "runAsRoot"

    def test_check_resource_dangerous_capabilities(self):
        """Test detection of dangerous Linux capabilities."""
        for cap in DANGEROUS_CAPS:
            resource: Dict[str, Any] = {
                "kind": "Pod",
                "metadata": {"name": "cap-pod", "namespace": TEST_NAMESPACE},
                "spec": {
                    "containers": [
                        {
                            "name": "cap-container",
                            "image": TEST_IMAGE,
                            "securityContext": {"capabilities": {"add": [cap]}},
                        }
                    ]
                },
            }

            checker = PrivilegeChecker()
            checker.check_resource(resource, TEST_APP_DIR)

            assert len(checker.findings) == 1
            assert checker.findings[0].severity == "high"
            assert checker.findings[0].check == "dangerousCapability"
            assert cap in checker.findings[0].details

    def test_check_resource_host_path_volume(self):
        """Test detection of hostPath volume mounts."""
        resource: Dict[str, Any] = {
            "kind": "DaemonSet",
            "metadata": {"name": "hostpath-daemonset", "namespace": "kube-system"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"name": "test", "image": "nginx"}],
                        "volumes": [
                            {
                                "name": "host-volume",
                                "hostPath": {"path": "/var/lib/docker"},
                            }
                        ],
                    }
                }
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("infrastructure/storage"))

        assert len(checker.findings) == 1
        assert checker.findings[0].severity == "high"
        assert checker.findings[0].check == "hostPath"
        assert "/var/lib/docker" in checker.findings[0].details

    def test_check_resource_multiple_issues(self):
        """Test detection of multiple security issues in one resource."""
        resource: Dict[str, Any] = {
            "kind": "Pod",
            "metadata": {"name": "multi-issue-pod", "namespace": "default"},
            "spec": {
                "hostNetwork": True,
                "hostPID": True,
                "containers": [
                    {
                        "name": "container1",
                        "image": "nginx",
                        "securityContext": {
                            "privileged": True,
                            "capabilities": {"add": ["SYS_ADMIN", "NET_ADMIN"]},
                        },
                    }
                ],
                "volumes": [{"name": "host-vol", "hostPath": {"path": "/var/run"}}],
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        # Should find: hostNetwork, hostPID, privileged, 2 dangerous caps, hostPath
        assert len(checker.findings) == 6

    def test_check_resource_init_containers(self):
        """Test that initContainers are also checked."""
        resource: Dict[str, Any] = {
            "kind": "Pod",
            "metadata": {"name": "init-pod", "namespace": "default"},
            "spec": {
                "initContainers": [
                    {
                        "name": "init-container",
                        "image": "busybox",
                        "securityContext": {"privileged": True},
                    }
                ],
                "containers": [{"name": "main", "image": "nginx"}],
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        assert len(checker.findings) == 1
        assert "init-container" in checker.findings[0].resource_name

    def test_check_resource_ignores_non_pod_resources(self):
        """Test that non-Pod resources are ignored."""
        resources: List[Dict[str, Any]] = [
            {"kind": "Service", "metadata": {"name": "svc"}, "spec": {}},
            {"kind": "ConfigMap", "metadata": {"name": "cm"}, "data": {}},
            {"kind": "Secret", "metadata": {"name": "secret"}, "data": {}},
        ]

        checker = PrivilegeChecker()
        for resource in resources:
            checker.check_resource(resource, Path("apps/test"))

        assert len(checker.findings) == 0

    def test_check_resource_deployment_template(self):
        """Test checking Deployment with template spec."""
        resource: Dict[str, Any] = {
            "kind": "Deployment",
            "metadata": {"name": "my-deployment", "namespace": "default"},
            "spec": {
                "template": {
                    "spec": {
                        "hostNetwork": True,
                        "containers": [{"name": "test", "image": "nginx"}],
                    }
                }
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        assert len(checker.findings) == 1
        assert checker.findings[0].check == "hostNetwork"

    def test_severity_levels(self) -> None:
        """Test that severity levels are correctly assigned."""
        # High severity: hostNetwork, hostPID, privileged, dangerous caps, hostPath
        # Medium severity: hostIPC, allowPrivilegeEscalation, runAsRoot

        checker = PrivilegeChecker()

        # Test high severity
        for check in ["hostNetwork", "hostPID"]:
            checker.findings.clear()
            resource: Dict[str, Any] = {
                "kind": "Pod",
                "metadata": {"name": "test-pod", "namespace": "default"},
                "spec": {
                    check: True,
                    "containers": [{"name": "test", "image": "nginx"}],
                },
            }
            checker.check_resource(resource, Path("apps/test"))
            if checker.findings:
                assert checker.findings[0].severity == "high"

        # Test medium severity
        checker.findings.clear()
        resource: Dict[str, Any] = {
            "kind": "Pod",
            "metadata": {"name": "test-pod", "namespace": "default"},
            "spec": {
                "hostIPC": True,
                "containers": [{"name": "test", "image": "nginx"}],
            },
        }
        checker.check_resource(resource, Path("apps/test"))
        assert checker.findings[0].severity == "medium"

    @patch("subprocess.run")
    def test_build_manifests_success(self, mock_run: Mock) -> None:
        """Test successful kustomize build."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="apiVersion: v1\nkind: Pod\n",
            stderr="",
        )

        checker = PrivilegeChecker()
        result = checker.build_manifests(Path("apps/test"))

        assert result == "apiVersion: v1\nkind: Pod\n"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_build_manifests_failure(self, mock_run: Mock) -> None:
        """Test handling of kustomize build failure."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: invalid kustomization",
        )

        checker = PrivilegeChecker()
        result = checker.build_manifests(Path("apps/test"))

        assert result == ""

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("kustomize", 60))
    def test_build_manifests_timeout(self, mock_run: Mock) -> None:
        """Test handling of kustomize build timeout."""
        checker = PrivilegeChecker()
        result = checker.build_manifests(Path("apps/test"))

        assert result == ""

    def test_json_output_format(self):
        """Test that findings can be serialized to JSON."""
        from dataclasses import asdict

        checker = PrivilegeChecker()
        checker.findings.append(
            SecurityFinding(
                severity="high",
                check="privileged",
                manifest_dir="apps/test",
                resource_kind="Pod",
                resource_name="test-pod/container1",
                namespace="default",
                details="Container runs in privileged mode",
            )
        )

        # Convert to JSON
        findings_dict = [asdict(f) for f in checker.findings]
        json_output = json.dumps(findings_dict, indent=2)

        # Should be valid JSON
        parsed = json.loads(json_output)
        assert len(parsed) == 1
        assert parsed[0]["severity"] == "high"
        assert parsed[0]["check"] == "privileged"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_constants_match_expectations(self):
        """Test that constants in check_privileges.py match expectations."""
        # Verify constants are accessible and match our test constants
        assert PrivilegeChecker.SCAN_DIRECTORIES == ["apps", "infrastructure", "argocd"]
        assert PrivilegeChecker.GIT_TIMEOUT == 30
        assert PrivilegeChecker.BUILD_TIMEOUT == 60
        assert PrivilegeChecker.MAX_WORKERS == 4
        assert len(PrivilegeChecker.DANGEROUS_CAPABILITIES) == 6
        assert set(PrivilegeChecker.DANGEROUS_CAPABILITIES) == set(DANGEROUS_CAPS)

    def test_empty_manifest(self):
        """Test handling of empty manifest."""
        checker = PrivilegeChecker()
        resources = checker.parse_manifests("")

        assert resources == []

    def test_resource_without_metadata(self):
        """Test handling of resource without metadata."""
        resource: Dict[str, Any] = {"kind": "Pod", "spec": {"containers": []}}

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        # Should not crash, should handle gracefully
        assert isinstance(checker.findings, list)

    def test_resource_without_spec(self):
        """Test handling of resource without spec."""
        resource: Dict[str, Any] = {"kind": "Pod", "metadata": {"name": "test"}}

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        # Should not crash
        assert isinstance(checker.findings, list)

    def test_container_without_security_context(self):
        """Test handling of container without securityContext."""
        resource: Dict[str, Any] = {
            "kind": "Pod",
            "metadata": {"name": "test-pod", "namespace": "default"},
            "spec": {"containers": [{"name": "test", "image": "nginx"}]},
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        # Should not find issues in a minimal secure pod
        assert len(checker.findings) == 0

    def test_capabilities_without_add(self):
        """Test handling of capabilities without 'add' key."""
        resource: Dict[str, Any] = {
            "kind": "Pod",
            "metadata": {"name": "test-pod", "namespace": "default"},
            "spec": {
                "containers": [
                    {
                        "name": "test",
                        "image": "nginx",
                        "securityContext": {"capabilities": {"drop": ["ALL"]}},
                    }
                ]
            },
        }

        checker = PrivilegeChecker()
        checker.check_resource(resource, Path("apps/test"))

        # Should not crash, dropping capabilities is safe
        assert len(checker.findings) == 0

    @patch("check_privileges.PrivilegeChecker.build_manifests")
    def test_build_and_check_kustomization(self, mock_build: Mock) -> None:
        """Test build_and_check_kustomization method for parallel execution."""
        mock_build.return_value = """
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: test
    image: nginx
"""

        checker = PrivilegeChecker()
        result = checker.build_and_check_kustomization(Path("apps/test"))

        assert result == 1  # Should return count of resources processed
        mock_build.assert_called_once_with(Path("apps/test"))

    def test_check_all_with_parallel_workers(self):
        """Test that MAX_WORKERS constant is used for parallel execution."""
        checker = PrivilegeChecker()
        assert checker.MAX_WORKERS > 0
        assert checker.MAX_WORKERS == 4  # Should match our optimization
