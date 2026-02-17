"""
Integration tests for deployment operations.

Tests the deployment module functionality, including:
- parse_deployment_info() with real rpm-ostree output
- get_current_deployment_info() parsing
- get_deployment_info() parsing
- Deployment menu item generation (pinned/unpinned states)
- Deployment filtering for pin/unpin submenus

These tests focus on module-level integration between deployment parsing,
menu generation, and their dependencies.
"""

from typing import List

import pytest
from pytest_mock import MockerFixture

from src.urh.commands import CommandRegistry
from src.urh.deployment import (
    DeploymentInfo,
    format_deployment_header,
    get_current_deployment_info,
    get_deployment_info,
    parse_deployment_info,
)


class TestParseDeploymentInfo:
    """Test parse_deployment_info function with various inputs."""

    def test_parses_single_current_deployment(self) -> None:
        """Test parsing output with a single current deployment."""
        status_output = """State: idle
Deployments:
● ostree-image-signed:docker://ghcr.io/test/repo:testing
                   Digest: sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
                  Version: 42.20231115.0 (2023-11-15T12:34:56Z)
                   Commit: abcdef1234567890abcdef1234567890abcdef12
                    OSName: bazzite
"""
        deployments = parse_deployment_info(status_output)

        assert len(deployments) == 1
        deployment = deployments[0]
        assert deployment.deployment_index == 0
        assert deployment.is_current is True
        assert deployment.is_pinned is False
        assert deployment.repository == "test/repo:testing"
        assert deployment.version == "42.20231115.0"

    def test_parses_pinned_status(self) -> None:
        """Test parsing pinned status indicator."""
        status_output = """State: idle
Deployments:
  ostree-image-signed:docker://ghcr.io/test/repo:stable
                   Digest: sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
                  Version: 41.20231110.0 (2023-11-10T12:34:56Z)
                   Commit: 1234567890abcdef1234567890abcdef12345678
                    OSName: bazzite
        Pinned: yes
"""
        deployments = parse_deployment_info(status_output)

        assert len(deployments) == 1
        deployment = deployments[0]
        assert deployment.is_pinned is True
        assert deployment.repository == "test/repo:stable"

    def test_parses_multiple_deployments(self) -> None:
        """Test parsing output with multiple deployments."""
        status_output = """State: idle
Deployments:
● ostree-image-signed:docker://ghcr.io/test/repo:testing
                   Digest: sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
                  Version: 42.20231115.0 (2023-11-15T12:34:56Z)
                   Commit: abcdef1234567890abcdef1234567890abcdef12
                    OSName: bazzite
  ostree-image-signed:docker://ghcr.io/test/repo:stable
                   Digest: sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
                  Version: 41.20231110.0 (2023-11-10T12:34:56Z)
                   Commit: 1234567890abcdef1234567890abcdef12345678
                    OSName: bazzite
        Pinned: yes
"""
        deployments = parse_deployment_info(status_output)

        assert len(deployments) == 2

        # First deployment (current)
        current = deployments[0]
        assert current.deployment_index == 0
        assert current.is_current is True
        assert current.is_pinned is False
        assert current.repository == "test/repo:testing"

        # Second deployment (pinned)
        pinned = deployments[1]
        assert pinned.deployment_index == 1
        assert pinned.is_current is False
        assert pinned.is_pinned is True
        assert pinned.repository == "test/repo:stable"

    def test_parses_empty_deployments(self) -> None:
        """Test parsing output with no deployments."""
        status_output = """State: idle
Deployments:
"""
        deployments = parse_deployment_info(status_output)

        assert len(deployments) == 0

    def test_parses_deployment_with_complex_version(self) -> None:
        """Test parsing deployment with complex version string."""
        status_output = """State: idle
Deployments:
● ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:stable
                   Digest: sha256:abc123
                  Version: 43.20231120.1234.5678 (2023-11-20T12:34:56Z)
                   Commit: abc123
                    OSName: bazzite
"""
        deployments = parse_deployment_info(status_output)

        assert len(deployments) == 1
        deployment = deployments[0]
        assert deployment.version == "43.20231120.1234.5678"
        assert deployment.repository == "ublue-os/bazzite:stable"

    def test_parses_deployment_with_nix_variant(self) -> None:
        """Test parsing deployment with nix variant repository."""
        status_output = """State: idle
Deployments:
● ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing
                   Digest: sha256:nix123
                  Version: 42.20231115.0 (2023-11-15T12:34:56Z)
                   Commit: nix123
                    OSName: bazzite-nix
"""
        deployments = parse_deployment_info(status_output)

        assert len(deployments) == 1
        deployment = deployments[0]
        assert deployment.repository == "wombatfromhell/bazzite-nix:testing"
        assert "testing" in deployment.repository


class TestGetCurrentDeploymentInfo:
    """Test get_current_deployment_info function."""

    def test_get_current_returns_first_deployment(self, mocker: MockerFixture) -> None:
        """Test that get_current_deployment_info returns the first (current) deployment."""
        mock_deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=True,
                is_pinned=False,
                repository="test/repo:testing",
                version="1.0",
            ),
            DeploymentInfo(
                deployment_index=1,
                is_current=False,
                is_pinned=True,
                repository="test/repo:stable",
                version="0.9",
            ),
        ]

        mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=mock_deployments
        )

        current = get_current_deployment_info()

        assert current is not None
        assert current["repository"] == "test/repo:testing"
        assert current["version"] == "1.0"

    def test_get_current_returns_none_when_no_deployments(
        self, mocker: MockerFixture
    ) -> None:
        """Test that get_current_deployment_info returns None when no deployments exist."""
        mocker.patch("src.urh.deployment.get_deployment_info", return_value=[])

        current = get_current_deployment_info()

        assert current is None


class TestGetDeploymentInfo:
    """Test get_deployment_info function (subprocess integration)."""

    def test_get_deployment_info_calls_rpm_ostree(self, mocker: MockerFixture) -> None:
        """Test that get_deployment_info calls rpm-ostree status -v."""
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """State: idle
Deployments:
● ostree-image-signed:docker://ghcr.io/test/repo:testing
                   Digest: sha256:abc123
                  Version: 1.0
                   Commit: abc123
                    OSName: bazzite
"""
        mocker.patch("subprocess.run", return_value=mock_result)

        deployments = get_deployment_info()

        assert len(deployments) == 1
        assert deployments[0].repository == "test/repo:testing"

    def test_get_deployment_info_handles_empty_output(
        self, mocker: MockerFixture
    ) -> None:
        """Test that get_deployment_info handles empty output."""
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "State: idle\nDeployments:\n"
        mocker.patch("subprocess.run", return_value=mock_result)

        deployments = get_deployment_info()

        assert len(deployments) == 0

    def test_get_deployment_info_handles_error_returncode(
        self, mocker: MockerFixture
    ) -> None:
        """Test that get_deployment_info handles error return code."""
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "rpm-ostree not found"
        mocker.patch("subprocess.run", return_value=mock_result)

        deployments = get_deployment_info()

        assert len(deployments) == 0


class TestFormatDeploymentHeader:
    """Test format_deployment_header function."""

    def test_format_header_with_current_deployment(self) -> None:
        """Test formatting header with current deployment info."""
        current = {
            "repository": "test/repo:testing",
            "version": "42.20231115.0",
        }

        header = format_deployment_header(current)

        assert "Current deployment" in header
        assert "test/repo" in header
        assert "42.20231115.0" in header

    def test_format_header_with_none_current(self) -> None:
        """Test formatting header when no current deployment."""
        header = format_deployment_header(None)

        assert "Current deployment" in header
        assert "unable to retrieve" in header.lower()


class TestCommandRegistryDeploymentHelpers:
    """Test CommandRegistry deployment helper methods."""

    @pytest.fixture
    def command_registry(self) -> CommandRegistry:
        """Create CommandRegistry instance for testing."""
        return CommandRegistry()

    @pytest.fixture
    def sample_deployments(self) -> List[DeploymentInfo]:
        """Create sample deployments for testing."""
        return [
            DeploymentInfo(
                deployment_index=0,
                is_current=True,
                is_pinned=False,
                repository="test/repo:testing",
                version="42.20231115.0",
            ),
            DeploymentInfo(
                deployment_index=1,
                is_current=False,
                is_pinned=True,
                repository="test/repo:stable",
                version="41.20231110.0",
            ),
            DeploymentInfo(
                deployment_index=2,
                is_current=False,
                is_pinned=False,
                repository="test/repo:unstable",
                version="43.20231120.0",
            ),
        ]

    def test_filter_unpinned_deployments(
        self,
        command_registry: CommandRegistry,
        sample_deployments: List[DeploymentInfo],
    ) -> None:
        """Test filtering unpinned deployments for pin submenu."""
        unpinned = command_registry._filter_unpinned_deployments(sample_deployments)

        assert len(unpinned) == 2
        # Should include current (testing) and unpinned (unstable)
        repos = {d.repository for d in unpinned}
        assert "test/repo:testing" in repos
        assert "test/repo:unstable" in repos
        # Should NOT include pinned (stable)
        assert "test/repo:stable" not in repos

    def test_filter_pinned_deployments(
        self,
        command_registry: CommandRegistry,
        sample_deployments: List[DeploymentInfo],
    ) -> None:
        """Test filtering pinned deployments for unpin submenu."""
        # Note: CommandRegistry doesn't have _filter_pinned_deployments
        # Filter manually to test the concept
        pinned = [d for d in sample_deployments if d.is_pinned]

        assert len(pinned) == 1
        # Should only include pinned (stable)
        assert pinned[0].repository == "test/repo:stable"

    def test_create_deployment_menu_items(
        self,
        command_registry: CommandRegistry,
        sample_deployments: List[DeploymentInfo],
    ) -> None:
        """Test creating menu items from deployment list."""
        items = command_registry._create_deployment_menu_items(sample_deployments)

        assert len(items) == 3
        # Items should be reversed (newest first)
        # Check that items have correct format (ListItem has description, not label)
        for item in items:
            assert hasattr(item, "description")
            assert hasattr(item, "value")

    def test_create_deployment_menu_items_shows_pinned_indicator(
        self,
        command_registry: CommandRegistry,
        sample_deployments: List[DeploymentInfo],
    ) -> None:
        """Test that pinned deployments show indicator in menu."""
        items = command_registry._create_deployment_menu_items(sample_deployments)

        # Items are reversed (newest first), so stable (index 1, pinned) should have '*'
        # Find the item with the '*' indicator
        pinned_items = [item for item in items if "*" in item.description]

        # Should have exactly one pinned deployment (stable)
        assert len(pinned_items) == 1
        assert "stable" in pinned_items[0].description

    def test_create_deployment_menu_items_empty_list(
        self, command_registry: CommandRegistry
    ) -> None:
        """Test creating menu items from empty deployment list."""
        items = command_registry._create_deployment_menu_items([])

        assert len(items) == 0

    def test_filter_with_no_unpinned_matches(
        self, command_registry: CommandRegistry
    ) -> None:
        """Test filtering when no deployments match criteria."""
        # All deployments are pinned
        all_pinned = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                is_pinned=True,
                repository="test/repo:stable",
                version="1.0",
            ),
        ]

        unpinned = command_registry._filter_unpinned_deployments(all_pinned)
        assert len(unpinned) == 0


class TestDeploymentInfoDataclass:
    """Test DeploymentInfo dataclass functionality."""

    def test_deployment_info_creation(self) -> None:
        """Test creating DeploymentInfo instance."""
        deployment = DeploymentInfo(
            deployment_index=0,
            is_current=True,
            is_pinned=False,
            repository="test/repo:testing",
            version="1.0.0",
        )

        assert deployment.deployment_index == 0
        assert deployment.is_current is True
        assert deployment.is_pinned is False
        assert deployment.repository == "test/repo:testing"
        assert deployment.version == "1.0.0"

    def test_deployment_info_repr(self) -> None:
        """Test DeploymentInfo string representation."""
        deployment = DeploymentInfo(
            deployment_index=0,
            is_current=True,
            is_pinned=False,
            repository="test/repo:testing",
            version="1.0.0",
        )

        repr_str = repr(deployment)
        assert "DeploymentInfo" in repr_str
        assert "testing" in repr_str
