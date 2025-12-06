"""Tests for the deployment module."""

import subprocess

import pytest

from src.urh.deployment import (
    DeploymentInfo,
    format_deployment_header,
    get_current_deployment_info,
    get_deployment_info,
    get_status_output,
    parse_deployment_info,
)


class TestDeployment:
    """Test deployment functionality."""

    def test_get_status_output_error(self, mocker):
        """Test getting status output when subprocess fails."""

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["rpm-ostree"]),
        )
        output = get_status_output()
        assert output is None

    def test_parse_deployment_info(self):
        """Test parsing deployment information from status output."""
        status_output = """State: idle
AutomaticUpdates: disabled
Deployments:
● ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing (index: 0)
                   Digest: sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
                  Version: 42.20231115.0 (2023-11-15T12:34:56Z)
                   Commit: abcdef1234567890abcdef1234567890abcdef12
                    OSName: bazzite
  ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:stable (index: 1)
                   Digest: sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
                  Version: 41.20231110.0 (2023-11-10T12:34:56Z)
                   Commit: 1234567890abcdef1234567890abcdef12345678
                    OSName: bazzite
"""
        deployments = parse_deployment_info(status_output)

        assert len(deployments) == 2

        # Check first deployment (current)
        assert deployments[0].deployment_index == 0
        assert deployments[0].is_current is True
        assert deployments[0].repository == "wombatfromhell/bazzite-nix:testing"
        assert deployments[0].version == "42.20231115.0"
        assert deployments[0].is_pinned is False

        # Check second deployment
        assert deployments[1].deployment_index == 1
        assert deployments[1].is_current is False
        assert deployments[1].repository == "wombatfromhell/bazzite-nix:stable"
        assert deployments[1].version == "41.20231110.0"
        assert deployments[1].is_pinned is False

    def test_get_deployment_info(self, mocker):
        """Test getting deployment information."""
        mock_parse = mocker.patch("src.urh.deployment.parse_deployment_info")
        mock_get_status = mocker.patch("src.urh.deployment.get_status_output")

        mock_get_status.return_value = "test output"
        mock_parse.return_value = []

        result = get_deployment_info()

        mock_get_status.assert_called_once()
        mock_parse.assert_called_once_with("test output")
        assert result == []

    def test_get_current_deployment_info(self, mocker):
        """Test getting current deployment information."""
        mock_deployment_info = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                repository="bazzite-nix",
                version="41.20231110.0",
                is_pinned=False,
            ),
            DeploymentInfo(
                deployment_index=1,
                is_current=True,
                repository="bazzite-nix",
                version="42.20231115.0",
                is_pinned=False,
            ),
        ]

        mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=mock_deployment_info
        )

        result = get_current_deployment_info()

        assert result == {"repository": "bazzite-nix", "version": "42.20231115.0"}

    def test_get_current_deployment_info_none(self, mocker):
        """Test getting current deployment information when none is available."""
        mocker.patch("src.urh.deployment.get_deployment_info", return_value=[])

        result = get_current_deployment_info()

        assert result is None

    @pytest.mark.parametrize(
        "deployment_info,expected",
        [
            (
                {"repository": "bazzite-nix", "version": "42.20231115.0"},
                "Current deployment: bazzite-nix (42.20231115.0)",
            ),
            (
                None,
                "Current deployment: System Information: Unable to retrieve deployment info",
            ),
            (
                {},
                "Current deployment: System Information: Unable to retrieve deployment info",
            ),
        ],
    )
    def test_format_deployment_header(self, deployment_info, expected):
        """Test formatting deployment header."""
        header = format_deployment_header(deployment_info)
        assert header == expected


class TestDeploymentIntegration:
    """Test deployment management integration."""

    def test_deployment_parsing_workflow(self):
        """Test complete deployment parsing workflow."""
        status_output = """State: idle
AutomaticUpdates: disabled
Deployments:
● ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing
                   Digest: sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
                  Version: 42.20231115.0 (2023-11-15T12:34:56Z)
                   Commit: abcdef1234567890abcdef1234567890abcdef12
                    OSName: bazzite
  ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:stable
                   Digest: sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
                  Version: 41.20231110.0 (2023-11-10T12:34:56Z)
                   Commit: 1234567890abcdef1234567890abcdef12345678
                    OSName: bazzite
"""

        # Parse deployment info
        deployments = parse_deployment_info(status_output)
        assert len(deployments) == 2

        # Get current deployment info
        current_deployment = None
        for deployment in deployments:
            if deployment.is_current:
                current_deployment = {
                    "repository": deployment.repository,
                    "version": deployment.version,
                }
                break

        assert current_deployment == {
            "repository": "wombatfromhell/bazzite-nix:testing",
            "version": "42.20231115.0",
        }

        # Format deployment header
        header = format_deployment_header(current_deployment)
        assert (
            header == "Current deployment: wombatfromhell/bazzite-nix (42.20231115.0)"
        )

    def test_deployment_info_with_pinned(self):
        """Test deployment parsing with pinned deployments."""
        status_output = """State: idle
AutomaticUpdates: disabled
Deployments:
● ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing
                   Digest: sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
                  Version: 42.20231115.0 (2023-11-15T12:34:56Z)
                   Commit: abcdef1234567890abcdef1234567890abcdef12
                    OSName: bazzite
  ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:stable
                   Digest: sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
                  Version: 41.20231110.0 (2023-11-10T12:34:56Z)
                   Commit: 1234567890abcdef1234567890abcdef12345678
                    OSName: bazzite
        Pinned: yes
"""

        # Parse deployment info
        deployments = parse_deployment_info(status_output)
        assert len(deployments) == 2

        # Check first deployment (current, not pinned)
        assert deployments[0].deployment_index == 0
        assert deployments[0].is_current is True
        assert deployments[0].repository == "wombatfromhell/bazzite-nix:testing"
        assert deployments[0].version == "42.20231115.0"
        assert deployments[0].is_pinned is False

        # Check second deployment (not current, pinned)
        assert deployments[1].deployment_index == 1
        assert deployments[1].is_current is False
        assert deployments[1].repository == "wombatfromhell/bazzite-nix:stable"
        assert deployments[1].version == "41.20231110.0"
        assert deployments[1].is_pinned is True
