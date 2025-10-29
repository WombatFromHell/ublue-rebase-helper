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
        # Mock isatty to return True so gum will be used
        mocker.patch("urh.os.isatty", return_value=True)

        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "rebase - Rebase to a container image"  # gum returns the selected command with description
        mocker.patch("urh.subprocess.run", return_value=mock_result)

        result = show_command_menu()
        assert result == "rebase"

    def test_show_command_menu_gum_not_found(self, mocker: MockerFixture):
        """Test show_command_menu when gum is not found."""
        # Mock isatty to return True so gum will be attempted
        mocker.patch("urh.os.isatty", return_value=True)
        mocker.patch("urh.subprocess.run", side_effect=FileNotFoundError)
        mock_print = mocker.patch("urh.print")

        result = show_command_menu()
        assert result == ""
        # Check that print was called to show available commands
        assert mock_print.called
