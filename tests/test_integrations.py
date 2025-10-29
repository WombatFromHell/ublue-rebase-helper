"""Integration tests for ublue-rebase-helper (urh.py)."""

import sys
import os
from pytest_mock import MockerFixture

# Add the parent directory to sys.path so we can import urh
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urh import show_command_menu


class TestShowCommandMenu:
    """Integration tests for the show_command_menu function."""

    def test_show_command_menu_with_selection(self, mocker: MockerFixture):
        """Test show_command_menu when a command is selected."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "rebase - Rebase to a container image"  # gum returns the selected command with description
        mock_subprocess_run.return_value = mock_result

        result = show_command_menu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )
        assert result == "rebase"

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
        assert result == ""
        # Check that print was called to show available commands
        assert mock_print.called
