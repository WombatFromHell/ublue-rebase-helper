"""End-to-end tests for ublue-rebase-helper (urh.py)."""

import sys
import os
from pytest_mock import MockerFixture

# Add the parent directory to sys.path so we can import urh
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urh import main


class TestMainE2E:
    """End-to-end tests for the main function."""

    def test_main_no_args_shows_menu(self, mocker: MockerFixture):
        """Test main shows menu when no arguments provided."""
        # Mock sys.argv to simulate no command-line arguments
        mocker.patch.object(sys, "argv", ["urh.py"])

        # Mock the show_command_menu to return empty string (no command to execute)
        mock_show_command_menu = mocker.patch("urh.show_command_menu", return_value="")

        # Mock sys.exit to avoid actual exit
        mock_sys_exit = mocker.patch("urh.sys.exit")

        # Call main function
        main()

        # Verify that show_command_menu was called
        mock_show_command_menu.assert_called_once()

        # Verify that sys.exit was called with code 0 (normal exit)
        mock_sys_exit.assert_called_once_with(0)

    def test_main_unknown_command(self, mocker: MockerFixture):
        """Test main shows help for unknown command."""
        # Mock sys.argv to simulate an unknown command
        mocker.patch.object(sys, "argv", ["urh.py", "unknown"])

        # Mock sys.exit so it doesn't actually exit
        mocker.patch("urh.sys.exit")

        # Mock the help_command to avoid actual printing
        mock_help_command = mocker.patch("urh.help_command")

        # Call main function
        main()

        # Verify that help_command was called with empty args
        mock_help_command.assert_called_once_with([])

    def test_main_calls_rebase(self, mocker: MockerFixture):
        """Test main calls rebase command when rebase is specified."""
        # Mock sys.argv to simulate 'rebase' command with URL
        mocker.patch.object(sys, "argv", ["urh.py", "rebase", "test-url"])

        # Mock sys.exit so it doesn't actually exit
        mocker.patch("urh.sys.exit")

        # Mock the rebase_command to avoid actual execution
        mock_rebase_command = mocker.patch("urh.rebase_command")

        # Call main function
        main()

        # Verify that rebase_command was called with the correct arguments
        mock_rebase_command.assert_called_once_with(["test-url"])

    def test_main_calls_check_command(self, mocker: MockerFixture):
        """Test main calls check command when check is specified."""
        # Mock sys.argv to simulate 'check' command
        mocker.patch.object(sys, "argv", ["urh.py", "check"])

        # Mock sys.exit so it doesn't actually exit
        mocker.patch("urh.sys.exit")

        # Mock the check_command to avoid actual execution
        mock_check_command = mocker.patch("urh.check_command")

        # Call main function
        main()

        # Verify that check_command was called with empty args
        mock_check_command.assert_called_once_with([])

    def test_main_calls_ls_command(self, mocker: MockerFixture):
        """Test main calls ls command when ls is specified."""
        # Mock sys.argv to simulate 'ls' command
        mocker.patch.object(sys, "argv", ["urh.py", "ls"])

        # Mock sys.exit so it doesn't actually exit
        mocker.patch("urh.sys.exit")

        # Mock the ls_command to avoid actual execution
        mock_ls_command = mocker.patch("urh.ls_command")

        # Call main function
        main()

        # Verify that ls_command was called with empty args
        mock_ls_command.assert_called_once_with([])

    def test_main_calls_rollback_command(self, mocker: MockerFixture):
        """Test main calls rollback command when rollback is specified."""
        # Mock sys.argv to simulate 'rollback' command
        mocker.patch.object(sys, "argv", ["urh.py", "rollback"])

        # Mock sys.exit so it doesn't actually exit
        mocker.patch("urh.sys.exit")

        # Mock the rollback_command to avoid actual execution
        mock_rollback_command = mocker.patch("urh.rollback_command")

        # Call main function
        main()

        # Verify that rollback_command was called with empty args
        mock_rollback_command.assert_called_once_with([])
