"""Integration tests for ublue-rebase-helper (urh.py)."""

import os
import sys

import pytest
from pytest_mock import MockerFixture

# Add the parent directory to sys.path so we can import urh
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urh import (
    show_command_menu,
    show_deployment_submenu,
    show_rebase_submenu,
    show_remote_ls_submenu,
)


class TestShowCommandMenu:
    """Integration tests for the show_command_menu function."""

    @pytest.mark.parametrize(
        "selected_option,expected_result",
        [
            ("rebase - Rebase to a container image", "rebase"),
            ("check - Check for available updates", "check"),
            ("upgrade - Upgrade to the latest version", "upgrade"),
            ("ls - List deployments with details", "ls"),
            ("rollback - Roll back to the previous deployment", "rollback"),
            ("pin - Pin a deployment", "pin"),
            ("unpin - Unpin a deployment", "unpin"),
            ("rm - Remove a deployment", "rm"),
        ],
    )
    def test_show_command_menu_with_selection(
        self, mocker: MockerFixture, selected_option: str, expected_result: str
    ):
        """Test show_command_menu when different commands are selected."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = selected_option
        mock_subprocess_run.return_value = mock_result

        result = show_command_menu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )
        assert result == expected_result

    def test_show_command_menu_no_selection(self, mocker: MockerFixture):
        """Test show_command_menu when no command is selected (ESC pressed)."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # gum returns 1 when no selection made
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result
        mock_print = mocker.Mock()

        result = show_command_menu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )
        assert result is None
        # Verify that print was called to show "No command selected."
        mock_print.assert_called_with("No command selected.")

    def test_show_command_menu_gum_not_found(self, mocker: MockerFixture):
        """Test show_command_menu when gum is not found."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock(side_effect=FileNotFoundError)
        mock_print = mocker.Mock()

        result = show_command_menu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )
        assert result is None
        # Check that print was called to show available commands
        assert mock_print.called

    def test_show_command_menu_non_tty_context(self, mocker: MockerFixture):
        """Test show_command_menu in non-TTY context."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=False)  # Non-TTY context
        mock_print = mocker.Mock()

        result = show_command_menu(is_tty_func=mock_is_tty, print_func=mock_print)
        assert result is None
        # In non-TTY, it should show commands without gum
        mock_print.assert_any_call(
            "Not running in interactive mode. Available commands:"
        )


class TestShowRebaseSubmenu:
    """Integration tests for the show_rebase_submenu function."""

    @pytest.mark.parametrize(
        "selected_option,expected_url",
        [
            ("ghcr.io/ublue-os/bazzite:stable", "ghcr.io/ublue-os/bazzite:stable"),
            ("ghcr.io/ublue-os/bazzite:testing", "ghcr.io/ublue-os/bazzite:testing"),
            (
                "ghcr.io/ublue-os/bazzite:unstable",
                "ghcr.io/ublue-os/bazzite:unstable",
            ),
            (
                "ghcr.io/wombatfromhell/bazzite-nix:testing",
                "ghcr.io/wombatfromhell/bazzite-nix:testing",
            ),
            (
                "ghcr.io/wombatfromhell/bazzite-nix:stable",
                "ghcr.io/wombatfromhell/bazzite-nix:stable",
            ),
            ("ghcr.io/astrovm/amyos:latest", "ghcr.io/astrovm/amyos:latest"),
        ],
    )
    def test_show_rebase_submenu_with_selection(
        self, mocker: MockerFixture, selected_option: str, expected_url: str
    ):
        """Test show_rebase_submenu when different container URLs are selected."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = selected_option
        mock_subprocess_run.return_value = mock_result

        result = show_rebase_submenu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )
        assert result == expected_url

    def test_show_rebase_submenu_no_selection(self, mocker: MockerFixture):
        """Test show_rebase_submenu when no option is selected."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # gum returns 1 when no selection made
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result
        mock_print = mocker.Mock()

        result = show_rebase_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )
        assert result is None
        mock_print.assert_called_with("No option selected.")

    def test_show_rebase_submenu_gum_not_found(self, mocker: MockerFixture):
        """Test show_rebase_submenu when gum is not found."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock(side_effect=FileNotFoundError)
        mock_print = mocker.Mock()

        result = show_rebase_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )
        assert result is None
        # Check that print was called to show available commands
        assert mock_print.called


class TestShowRemoteLsSubmenuIntegration:
    """Integration tests for the show_remote_ls_submenu function."""

    @pytest.mark.parametrize(
        "selected_option,expected_url",
        [
            ("ghcr.io/ublue-os/bazzite:stable", "ghcr.io/ublue-os/bazzite:stable"),
            ("ghcr.io/ublue-os/bazzite:testing", "ghcr.io/ublue-os/bazzite:testing"),
            (
                "ghcr.io/ublue-os/bazzite:unstable",
                "ghcr.io/ublue-os/bazzite:unstable",
            ),
            (
                "ghcr.io/wombatfromhell/bazzite-nix:testing",
                "ghcr.io/wombatfromhell/bazzite-nix:testing",
            ),
            (
                "ghcr.io/wombatfromhell/bazzite-nix:stable",
                "ghcr.io/wombatfromhell/bazzite-nix:stable",
            ),
            ("ghcr.io/astrovm/amyos:latest", "ghcr.io/astrovm/amyos:latest"),
        ],
    )
    def test_show_remote_ls_submenu_with_selection(
        self, mocker: MockerFixture, selected_option: str, expected_url: str
    ):
        """Test show_remote_ls_submenu when different container URLs are selected."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = selected_option
        mock_subprocess_run.return_value = mock_result

        result = show_remote_ls_submenu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )
        assert result == expected_url

    def test_show_remote_ls_submenu_no_selection(self, mocker: MockerFixture):
        """Test show_remote_ls_submenu when no option is selected."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # gum returns 1 when no selection made
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result
        mock_print = mocker.Mock()

        result = show_remote_ls_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )
        assert result is None
        mock_print.assert_called_with("No option selected.")

    def test_show_remote_ls_submenu_gum_not_found(self, mocker: MockerFixture):
        """Test show_remote_ls_submenu when gum is not found."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock(side_effect=FileNotFoundError)
        mock_print = mocker.Mock()

        result = show_remote_ls_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )
        assert result is None
        # Check that print was called to show available commands
        assert mock_print.called


class TestShowDeploymentSubmenuIntegration:
    """Integration tests for the show_deployment_submenu function."""

    def test_show_deployment_submenu_with_selection(self, mocker: MockerFixture):
        """Test show_deployment_submenu when a deployment is selected."""
        # Mock parsed deployments
        mock_deployments = [
            {
                "index": 0,
                "version": "testing-43.20251028.9 (2025-10-29T06:23:42Z)",
                "pinned": False,
            },
            {
                "index": 1,
                "version": "testing-43.20251028.5 (2025-10-28T13:56:45Z)",
                "pinned": True,
            },
        ]
        mocker.patch("urh.parse_deployments", return_value=mock_deployments)

        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "testing-43.20251028.5 (2025-10-28T13:56:45Z) [Pinned: Yes]"
        )
        mock_subprocess_run.return_value = mock_result

        result = show_deployment_submenu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )
        assert result == 1  # Should return the index of the selected deployment

    def test_show_deployment_submenu_with_filter(self, mocker: MockerFixture):
        """Test show_deployment_submenu with a filter function."""
        # Mock parsed deployments
        mock_deployments = [
            {
                "index": 0,
                "version": "testing-43.20251028.9 (2025-10-29T06:23:42Z)",
                "pinned": False,
            },
            {
                "index": 1,
                "version": "testing-43.20251028.5 (2025-10-28T13:56:45Z)",
                "pinned": True,
            },
        ]
        mocker.patch("urh.parse_deployments", return_value=mock_deployments)

        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "testing-43.20251028.5 (2025-10-28T13:56:45Z) [Pinned: Yes]"
        )
        mock_subprocess_run.return_value = mock_result

        # Define a filter function for pinned deployments only
        def pinned_filter(deployment):
            return deployment["pinned"]

        result = show_deployment_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            filter_func=pinned_filter,
        )
        assert result == 1  # Should return the index of the selected pinned deployment


class TestTOMLFilterRulesIntegration:
    """Integration tests for TOML filter rules and specific repository handling."""

    def test_astrovm_amyos_latest_context_filtering(self, mocker: MockerFixture):
        """Test that astrovm/amyos with :latest context properly filters to YYYYMMDD format tags."""
        from urh import TOMLFilterRules

        # Create filter rules for astrovm/amyos repository
        rules = TOMLFilterRules("astrovm/amyos")

        # Test with raw tags that include latest. format tags that should be transformed
        raw_tags = [
            "latest.20251031",  # Should transform to 20251031 and be preserved for :latest context
            "latest.20251030",  # Should transform to 20251030 and be preserved for :latest context
            "latest.20251029",  # Should transform to 20251029 and be preserved for :latest context
            "stable-42.20250610",  # Should be filtered out in :latest context
            "42.20250610",  # Should be filtered out in :latest context
            "latest.",  # Should be filtered out by general filter
            "latest.abc",  # Should be filtered out by general filter
        ]

        # Apply context-aware filtering for 'latest' context
        result = rules.context_aware_filter_and_sort(raw_tags, "latest")

        # Verify that only YYYYMMDD format tags from transformed latest.YYYYMMDD are returned
        expected_tags = ["20251031", "20251030", "20251029"]
        assert result == expected_tags, f"Expected {expected_tags}, got {result}"

    def test_astrovm_amyos_latest_context_with_duplicates(self, mocker: MockerFixture):
        """Test that astrovm/amyos with :latest context properly handles duplicates."""
        from urh import TOMLFilterRules

        # Create filter rules for astrovm/amyos repository
        rules = TOMLFilterRules("astrovm/amyos")

        # Test with tags that could create duplicates: both original YYYYMMDD and latest.YYYYMMDD
        raw_tags = [
            "latest.20251031",  # Should transform to 20251031
            "20251031",  # Already in YYYYMMDD format - potential duplicate
            "latest.20251030",  # Should transform to 20251030
            "20251030",  # Already in YYYYMMDD format - potential duplicate
            "latest.20251029",  # Should transform to 20251029
            "20251028",  # Should be kept (no duplicate)
        ]

        # Apply context-aware filtering for 'latest' context
        result = rules.context_aware_filter_and_sort(raw_tags, "latest")

        # Verify that duplicates are properly handled and only unique tags are returned
        # Should contain each date only once: 20251031, 20251030, 20251029, 20251028
        expected_tags = ["20251031", "20251030", "20251029", "20251028"]
        assert len(result) == len(expected_tags), (
            f"Expected {len(expected_tags)} tags, got {len(result)}"
        )
        for tag in expected_tags:
            assert tag in result, f"Expected tag {tag} not found in result {result}"

    def test_astrovm_amyos_non_latest_context_filtering(self, mocker: MockerFixture):
        """Test that astrovm/amyos with non-latest context applies normal filtering."""
        from urh import TOMLFilterRules

        # Create filter rules for astrovm/amyos repository
        rules = TOMLFilterRules("astrovm/amyos")

        # Test with raw tags using non-latest context
        raw_tags = [
            "latest.20251031",  # Should transform to 20251031
            "stable-42.20250610",  # Should be preserved
            "42.20250610",  # Should be preserved
            "latest.",  # Should be filtered out by general filter
            "latest.abc",  # Should be filtered out by general filter
        ]

        # Apply context-aware filtering for 'stable' context
        result = rules.context_aware_filter_and_sort(raw_tags, "stable")

        # With stable context, should only get tags with 'stable-' prefix
        expected_tags = ["stable-42.20250610"]
        assert result == expected_tags, f"Expected {expected_tags}, got {result}"

    def test_astrovm_amyos_transform_patterns_integration(self, mocker: MockerFixture):
        """Test that astrovm/amyos transform patterns work correctly in context filtering."""
        from urh import TOMLFilterRules

        # Create filter rules for astrovm/amyos repository
        rules = TOMLFilterRules("astrovm/amyos")

        # Test specific transformation of latest.YYYYMMDD to YYYYMMDD format
        raw_tags = [
            "latest.20251031",  # Should transform to 20251031
            "latest.20251030",  # Should transform to 20251030
            "latest.20241215",  # Should transform to 20241215
        ]

        # First test the transform functionality directly
        transformed = [rules.transform_tag(tag) for tag in raw_tags]
        expected_transformed = ["20251031", "20251030", "20241215"]
        assert transformed == expected_transformed, (
            f"Expected {expected_transformed}, got {transformed}"
        )

        # Then test with context filtering
        result = rules.context_aware_filter_and_sort(raw_tags, "latest")
        # Should get the transformed tags back
        assert result == expected_transformed, (
            f"Expected {expected_transformed}, got {result}"
        )

    def test_remote_ls_command_astrovm_amyos_latest_integration(
        self, mocker: MockerFixture
    ):
        """Integration test for remote_ls_command with astrovm/amyos:latest."""
        import io
        from contextlib import redirect_stdout

        from urh import OCIClient, remote_ls_command

        # Mock the OCIClient to return specific raw tags
        mock_client = mocker.Mock(spec=OCIClient)
        mock_client.get_raw_tags.return_value = {
            "tags": [
                "latest.20251031",  # Should transform and show for :latest context
                "latest.20251030",  # Should transform and show for :latest context
                "latest.20251029",  # Should transform and show for :latest context
                "stable-42.20250610",  # Should be filtered out
                "42.20250610",  # Should be filtered out
            ]
        }

        # Create actual TOMLFilterRules for astrovm/amyos to use in test
        from urh import TOMLFilterRules

        real_filter_rules = TOMLFilterRules("astrovm/amyos")
        mock_client.filter_rules = real_filter_rules

        # Patch the OCIClient constructor to return our mock
        mocker.patch("urh.OCIClient", return_value=mock_client)

        # Capture stdout to verify the output
        captured_output = io.StringIO()

        # Mock sys.exit to prevent actual exit
        mocker.patch("urh.sys.exit")

        # Run the command and capture output
        with redirect_stdout(captured_output):
            try:
                remote_ls_command(["ghcr.io/astrovm/amyos:latest"])
            except SystemExit:
                pass  # Expected due to sys.exit(0)

        output = captured_output.getvalue()

        # Verify that the output contains the expected tags
        assert "Tags for ghcr.io/astrovm/amyos:latest:" in output
        assert "20251031" in output
        assert "20251030" in output
        assert "20251029" in output
        # Ensure non-latest tags are not in the output
        assert "stable-42.20250610" not in output
        assert "42.20250610" not in output
