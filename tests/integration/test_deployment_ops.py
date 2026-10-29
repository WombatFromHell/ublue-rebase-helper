"""
Integration tests for deployment operations.

Tests the deployment module functionality, including:
- parse_deployment_info() with real rpm-ostree status --json output
- get_current_deployment_info() parsing
- get_deployment_info() parsing
- Deployment menu item generation (pinned/unpinned states)
- Deployment filtering for pin/unpin submenus

These tests focus on module-level integration between deployment parsing,
menu generation, and their dependencies.
"""

import json
import subprocess
from typing import Dict, List

import pytest
from pytest_mock import MockerFixture

from src.urh.commands.registry import CommandRegistry
from src.urh.deployment import (
    DeploymentInfo,
    format_deployment_header,
    format_deployment_summary,
    get_current_deployment_info,
    get_deployment_info,
    parse_deployment_info,
)


def status_json(deployments: List[Dict]) -> str:
    """Build rpm-ostree status --json output from deployment dicts."""
    return json.dumps({"deployments": deployments})


@pytest.mark.integration
class TestParseDeploymentInfo:
    """Test parse_deployment_info function with various inputs."""

    def test_parses_single_current_deployment(self) -> None:
        """Test parsing a booted container deployment."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "docker://ghcr.io/test/repo:testing",
                        "container-image-reference-digest": "sha256:abcdef",
                        "checksum": "abcdef",
                        "version": "42.20231115.0",
                        "pinned": False,
                        "serial": 0,
                    }
                ]
            )
        )

        assert len(deployments) == 1
        deployment = deployments[0]
        assert deployment.deployment_index == 0
        assert deployment.is_current is True
        assert deployment.is_pinned is False
        assert deployment.repository == "test/repo:testing"
        assert deployment.version == "42.20231115.0"

    def test_parses_pinned_status(self) -> None:
        """Test parsing pinned status indicator."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": False,
                        "container-image-reference": "docker://ghcr.io/test/repo:stable",
                        "version": "41.20231110.0",
                        "pinned": True,
                    }
                ]
            )
        )

        assert len(deployments) == 1
        deployment = deployments[0]
        assert deployment.is_pinned is True
        assert deployment.repository == "test/repo:stable"

    def test_parses_multiple_deployments_in_list_order(self) -> None:
        """Test that index is list position, which is the ostree admin pin/undeploy index."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "docker://ghcr.io/test/repo:testing",
                        "version": "42.20231115.0",
                        "pinned": False,
                        "serial": 0,
                    },
                    {
                        "booted": False,
                        "container-image-reference": "docker://ghcr.io/test/repo:stable",
                        "version": "41.20231110.0",
                        "pinned": True,
                        "serial": 0,
                    },
                ]
            )
        )

        assert len(deployments) == 2

        current = deployments[0]
        assert current.deployment_index == 0
        assert current.is_current is True
        assert current.is_pinned is False
        assert current.repository == "test/repo:testing"

        pinned = deployments[1]
        assert pinned.deployment_index == 1
        assert pinned.is_current is False
        assert pinned.is_pinned is True
        assert pinned.repository == "test/repo:stable"

    def test_index_is_not_the_deploy_serial(self) -> None:
        """Deploy serial is 0 for bootc images; it must not become the index."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "docker://ghcr.io/test/repo:a",
                        "serial": 0,
                    },
                    {
                        "booted": False,
                        "container-image-reference": "docker://ghcr.io/test/repo:b",
                        "serial": 0,
                    },
                ]
            )
        )

        assert [d.deployment_index for d in deployments] == [0, 1]

    def test_parses_empty_deployments(self) -> None:
        """Test parsing output with no deployments."""
        assert parse_deployment_info(status_json([])) == []

    def test_parses_deployment_with_complex_version(self) -> None:
        """Test parsing deployment with complex version string."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "docker://ghcr.io/ublue-os/bazzite:stable",
                        "version": "43.20231120.1234.5678",
                    }
                ]
            )
        )

        assert len(deployments) == 1
        assert deployments[0].version == "43.20231120.1234.5678"
        assert deployments[0].repository == "ublue-os/bazzite:stable"

    def test_parses_deployment_with_nix_variant(self) -> None:
        """Test parsing deployment with nix variant repository."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "docker://ghcr.io/wombatfromhell/bazzite-nix:testing",
                        "version": "42.20231115.0",
                    }
                ]
            )
        )

        assert deployments[0].repository == "wombatfromhell/bazzite-nix:testing"
        assert "testing" in deployments[0].repository

    def test_parses_bare_image_reference_without_transport(self) -> None:
        """container-image-reference may be bare (no docker:// transport)."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "ghcr.io/test/repo:stable",
                    }
                ]
            )
        )

        assert deployments[0].repository == "test/repo:stable"

    def test_parses_local_container_storage_reference(self) -> None:
        """Local containers-storage references keep owner/repo:tag without localhost."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "containers-storage:localhost/name:tag",
                    }
                ]
            )
        )

        assert deployments[0].repository == "name:tag"
        assert deployments[0].image_ref == "localhost/name:tag"

    def test_parses_untranslated_origin_for_non_container_deployments(self) -> None:
        """Traditional deployments have origin instead of container-image-reference."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "origin": "ostree://example:example",
                        "version": "1.0",
                    }
                ]
            )
        )

        assert deployments[0].repository == "example:example"

    def test_parses_verbose_details_for_ls(self) -> None:
        """ls needs the full image ref plus digest, commit, osname, timestamp, staged."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "docker://ghcr.io/wombatfromhell/bazzite-nix:unstable",
                        "container-image-reference-digest": "sha256:1c9dbd00",
                        "checksum": "80487394d4ec",
                        "osname": "bazzite-nix",
                        "version": "45.20261020.9",
                        "pinned": False,
                        "staged": False,
                        "requested-packages": ["htop"],
                    }
                ]
            )
        )

        deployment = deployments[0]
        assert deployment.image_ref == "ghcr.io/wombatfromhell/bazzite-nix:unstable"
        assert deployment.repository == "wombatfromhell/bazzite-nix:unstable"
        assert deployment.digest == "sha256:1c9dbd00"
        assert deployment.commit == "80487394d4ec"
        assert deployment.osname == "bazzite-nix"
        assert deployment.staged is False
        assert deployment.requested_packages == ["htop"]
        assert deployment.timestamp == ""

    def test_parses_timestamp_when_present(self) -> None:
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": False,
                        "container-image-reference": "docker://ghcr.io/test/repo:stable",
                        "version": "1.0",
                        "timestamp": 1792248404,
                        "staged": True,
                    }
                ]
            )
        )

        assert deployments[0].timestamp == "2026-10-17 14:46 UTC"
        assert deployments[0].staged is True

    def test_version_defaults_to_unknown_when_missing(self) -> None:
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "docker://ghcr.io/test/repo:x",
                    }
                ]
            )
        )

        assert deployments[0].version == "Unknown"

    def test_parses_booted_deployment_without_timestamp(self) -> None:
        """Regression: rpm-ostree status -v aborts when timestamp is missing; JSON must survive it."""
        deployments = parse_deployment_info(
            status_json(
                [
                    {
                        "booted": True,
                        "container-image-reference": "docker://ghcr.io/wombatfromhell/bazzite-nix:unstable",
                        "version": "45.20261020.9",
                        "pinned": False,
                    }
                ]
            )
        )

        assert len(deployments) == 1
        assert deployments[0].is_current is True

    @pytest.mark.parametrize(
        "bad_output",
        [
            "",
            "State: idle\nDeployments:",
            "not json",
            "[]",
            "{}",
            '{"deployments": null}',
        ],
    )
    def test_malformed_or_text_output_returns_no_deployments(
        self, bad_output: str
    ) -> None:
        assert parse_deployment_info(bad_output) == []


@pytest.mark.integration
class TestGetCurrentDeploymentInfo:
    """Test get_current_deployment_info function."""

    def test_get_current_returns_first_deployment(self, mocker: MockerFixture) -> None:
        """Test that get_current_deployment_info returns the current deployment."""
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


@pytest.mark.integration
class TestGetDeploymentInfo:
    """Test get_deployment_info function (subprocess integration)."""

    @pytest.fixture(autouse=True)
    def setup_deployment_mocks(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Setup mocks for deployment info tests."""
        # Mock rpm-ostree and ostree commands to prevent FileNotFoundError

    def test_get_deployment_info_calls_rpm_ostree_status_json(
        self, mocker: MockerFixture
    ) -> None:
        """Test that get_deployment_info uses rpm-ostree status --json."""
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = status_json(
            [
                {
                    "booted": True,
                    "container-image-reference": "docker://ghcr.io/test/repo:testing",
                    "version": "1.0.0",
                }
            ]
        )
        run = mocker.patch("subprocess.run", return_value=mock_result)

        deployments = get_deployment_info()

        assert len(deployments) == 1
        assert deployments[0].repository == "test/repo:testing"
        assert run.call_args[0][0] == ["rpm-ostree", "status", "--json"]

    def test_get_deployment_info_handles_empty_output(
        self, mocker: MockerFixture
    ) -> None:
        """Test that get_deployment_info handles empty output."""
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mocker.patch("subprocess.run", return_value=mock_result)

        deployments = get_deployment_info()

        assert len(deployments) == 0

    def test_get_deployment_info_handles_error_returncode(
        self, mocker: MockerFixture
    ) -> None:
        """Test that get_deployment_info handles error return code."""
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "rpm-ostreed:ERROR: assertion failed"
        mocker.patch("subprocess.run", return_value=mock_result)

        deployments = get_deployment_info()

        assert len(deployments) == 0

    def test_get_deployment_info_survives_aborted_verbose_status(
        self, mocker: MockerFixture
    ) -> None:
        """The SIGABRT bail-out must not raise out of get_deployment_info."""
        mock_result = mocker.MagicMock()
        mock_result.returncode = -6
        mock_result.stderr = "Bail out! rpm-ostreed:ERROR: assertion failed"
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                -6, ["rpm-ostree", "status", "--json"]
            ),
        )

        assert get_deployment_info() == []


@pytest.mark.integration
class TestFormatDeploymentHeader:
    """Test format_deployment_header function."""

    def test_format_header_with_current_deployment(self) -> None:
        """DeploymentInfo keeps the tag; the header shows the repository without it."""
        header = format_deployment_header(
            {"repository": "test/repo:testing", "version": "42.20231115.0"}
        )

        assert "Current deployment" in header
        assert "test/repo" in header
        assert "42.20231115.0" in header
        assert "testing" not in header

    def test_format_header_with_none_current(self) -> None:
        """Test formatting header when no current deployment."""
        header = format_deployment_header(None)

        assert "Current deployment" in header
        assert "unable to retrieve" in header.lower()


@pytest.mark.integration
class TestCommandRegistryDeploymentHelpers:
    """Test deployment helper functions from deployment_helpers module."""

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
        sample_deployments: List[DeploymentInfo],
    ) -> None:
        """Test filtering unpinned deployments for pin submenu."""
        from src.urh.commands.deployment_helpers import filter_unpinned_deployments

        unpinned = filter_unpinned_deployments(sample_deployments)

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
        pinned = [d for d in sample_deployments if d.is_pinned]

        assert len(pinned) == 1
        assert pinned[0].repository == "test/repo:stable"

    def test_create_deployment_menu_items(
        self,
        sample_deployments: List[DeploymentInfo],
    ) -> None:
        """Test creating menu items from deployment list."""
        from src.urh.commands.deployment_helpers import create_deployment_menu_items

        items = create_deployment_menu_items(sample_deployments)

        assert len(items) == 3
        for item in items:
            assert hasattr(item, "description")
            assert hasattr(item, "value")

    def test_create_deployment_menu_items_shows_pinned_indicator(
        self,
        sample_deployments: List[DeploymentInfo],
    ) -> None:
        """Test that pinned deployments show indicator in menu."""
        from src.urh.commands.deployment_helpers import create_deployment_menu_items

        items = create_deployment_menu_items(sample_deployments)

        # Items are reversed (newest first), so stable (index 1, pinned) has '*'
        pinned_items = [item for item in items if "*" in item.description]
        assert len(pinned_items) == 1
        assert "stable" in pinned_items[0].description

    def test_create_deployment_menu_items_empty_list(self) -> None:
        """Test creating menu items from empty deployment list."""
        from src.urh.commands.deployment_helpers import create_deployment_menu_items

        assert len(create_deployment_menu_items([])) == 0

    def test_filter_with_no_unpinned_matches(self) -> None:
        """Test filtering when no deployments match criteria."""
        from src.urh.commands.deployment_helpers import filter_unpinned_deployments

        all_pinned = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                is_pinned=True,
                repository="test/repo:stable",
                version="1.0",
            ),
        ]

        assert len(filter_unpinned_deployments(all_pinned)) == 0


class TestDeploymentInfoDataclass:
    """Test DeploymentInfo dataclass functionality."""

    def test_deployment_info_creation(self) -> None:
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


@pytest.mark.integration
class TestFormatDeploymentSummary:
    """Test format_deployment_summary used by urh ls."""

    def test_summary_shows_full_image_ref_and_details(self) -> None:
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=True,
                is_pinned=False,
                repository="wombatfromhell/bazzite-nix:unstable",
                version="45.20261020.9",
                image_ref="ghcr.io/wombatfromhell/bazzite-nix:unstable",
                digest="sha256:1c9dbd00",
                commit="80487394d4ec",
                osname="bazzite-nix",
                timestamp="2026-10-20 23:48 UTC",
            ),
            DeploymentInfo(
                deployment_index=1,
                is_current=False,
                is_pinned=True,
                repository="wombatfromhell/bazzite-nix:stable",
                version="44.20261012.1",
                image_ref="ghcr.io/wombatfromhell/bazzite-nix:stable",
                digest="sha256:60835f90",
                commit="24276b69254c",
                osname="bazzite-nix",
                staged=True,
            ),
        ]

        summary = format_deployment_summary(deployments)
        lines = summary.splitlines()

        assert lines[0] == "Deployments:"
        assert lines[2] == "● 0  ghcr.io/wombatfromhell/bazzite-nix:unstable"
        assert lines[3] == "    Version: 45.20261020.9 (2026-10-20 23:48 UTC)"
        assert lines[4] == "     Digest: sha256:1c9dbd00"
        assert lines[5] == "     Commit: 80487394d4ec"
        assert lines[6] == "     OSName: bazzite-nix"
        assert lines[7] == "     Staged: no"
        assert lines[8] == "     Pinned: no"
        assert lines[10] == "* 1  ghcr.io/wombatfromhell/bazzite-nix:stable"
        assert "     Staged: yes" in summary
        assert "     Pinned: yes" in summary
        assert "     Digest: sha256:60835f90" in summary
        assert "Indices match urh pin / unpin / rm / undeploy." in summary

    def test_summary_omits_absent_details(self) -> None:
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=True,
                is_pinned=False,
                repository="test/repo:testing",
                version="42.20231115.0",
                image_ref="ghcr.io/test/repo:testing",
            ),
        ]

        summary = format_deployment_summary(deployments)
        lines = summary.splitlines()

        assert lines[2] == "● 0  ghcr.io/test/repo:testing"
        assert lines[3] == "    Version: 42.20231115.0"
        assert "Digest" not in summary
        assert "OSName" not in summary

    def test_summary_omits_default_osname(self) -> None:
        """Container images always report osname 'default'; that line is noise."""
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=True,
                is_pinned=False,
                repository="test/repo:testing",
                version="1.0",
                image_ref="ghcr.io/test/repo:testing",
                osname="default",
            ),
        ]

        assert "OSName" not in format_deployment_summary(deployments)

    def test_summary_lists_layered_packages(self) -> None:
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=True,
                is_pinned=False,
                repository="test/repo:testing",
                version="1.0",
                image_ref="ghcr.io/test/repo:testing",
                requested_packages=["htop", "tmux"],
            ),
        ]

        assert "    Layered: htop, tmux" in format_deployment_summary(deployments)

    def test_summary_with_no_deployments(self) -> None:
        assert format_deployment_summary([]) == "No deployments found."
