"""Integration tests for ublue-rebase-helper (urh.py)."""

import sys
import os
import pytest
from pytest_mock import MockerFixture

# Add the parent directory to sys.path so we can import urh
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urh import (
    show_command_menu,
    show_rebase_submenu,
    show_remote_ls_submenu,
    show_deployment_submenu,
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
