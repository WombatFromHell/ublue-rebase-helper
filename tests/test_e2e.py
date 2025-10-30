"""End-to-end tests for ublue-rebase-helper (urh.py)."""

import sys
import os
import pytest
from pytest_mock import MockerFixture

# Add the parent directory to sys.path so we can import urh
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urh import main


class TestMainE2E:
    """End-to-end tests for the main function."""

    @pytest.mark.parametrize(
        "command,expected_func,expected_args",
        [
            ("rebase", "rebase_command", ["test-url"]),
            ("check", "check_command", []),
            ("ls", "ls_command", []),
            ("rollback", "rollback_command", []),
            ("upgrade", "upgrade_command", []),
            ("pin", "pin_command", ["1"]),
            ("unpin", "unpin_command", ["2"]),
            ("rm", "rm_command", ["3"]),
            ("remote-ls", "remote_ls_command", ["ghcr.io/test/repo:latest"]),
        ],
    )
    def test_main_calls_correct_command(
        self,
        mocker: MockerFixture,
        command: str,
        expected_func: str,
        expected_args: list,
    ):
        """Test main calls the correct command function with appropriate arguments."""
        # Prepare argv with command and its arguments
        argv = ["urh.py", command] + expected_args

        # Mock sys.argv to simulate the command
        mocker.patch.object(sys, "argv", argv)

        # Mock sys.exit so it doesn't actually exit
        mocker.patch("urh.sys.exit")

        # Mock the expected command function to track if it's called
        mock_command_func = mocker.patch(f"urh.{expected_func}")

        # Call main function
        main()

        # Verify that the correct command function was called with the right arguments
        mock_command_func.assert_called_once_with(expected_args)

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


class TestMainE2EErrorScenarios:
    """Additional end-to-end tests for error scenarios."""

    def test_main_with_invalid_args_for_number_commands(self, mocker: MockerFixture):
        """Test main handles invalid arguments for commands that expect numbers."""
        # Test invalid number for pin command
        mocker.patch.object(sys, "argv", ["urh.py", "pin", "invalid"])
        mock_print = mocker.patch("urh.print")
        mocker.patch("urh.sys.exit")

        main()

        # Should print error message about invalid number
        mock_print.assert_any_call("Invalid deployment number: invalid")

    def test_main_with_invalid_args_for_rebase(self, mocker: MockerFixture):
        """Test main with rebase command that will trigger submenu."""
        # This is more of a functional test, mocking the submenu behavior
        mocker.patch.object(sys, "argv", ["urh.py", "rebase"])
        mock_rebase = mocker.patch("urh.rebase_command")
        mocker.patch("urh.sys.exit")

        main()

        # Should call rebase command (rebase_command will handle submenu)
        # We're not going to test the full submenu flow here since it's an E2E test
        mock_rebase.assert_called_once()

    def test_main_multiple_args(self, mocker: MockerFixture):
        """Test main with commands that might have multiple arguments."""
        # Test rebase with full URL
        mocker.patch.object(
            sys, "argv", ["urh.py", "rebase", "ghcr.io/ublue-os/bazzite:latest"]
        )
        mock_rebase_command = mocker.patch("urh.rebase_command")
        mocker.patch("urh.sys.exit")

        main()

        # Should call rebase with the provided URL
        mock_rebase_command.assert_called_once_with(["ghcr.io/ublue-os/bazzite:latest"])

    def test_main_help_command(self, mocker: MockerFixture):
        """Test main with help command."""
        mocker.patch.object(sys, "argv", ["urh.py", "help"])
        mock_help_command = mocker.patch("urh.help_command")
        mocker.patch("urh.sys.exit")

        main()

        # Should call help command with empty arguments
        mock_help_command.assert_called_once_with([])

    def test_main_remote_ls_command_with_url(self, mocker: MockerFixture):
        """Test main with remote-ls command and specific URL."""
        # Mock sys.argv to simulate the remote-ls command with URL
        mocker.patch.object(
            sys, "argv", ["urh.py", "remote-ls", "ghcr.io/ublue-os/bazzite:latest"]
        )

        # Mock sys.exit so it doesn't actually exit
        mocker.patch("urh.sys.exit")

        # Mock the remote_ls_command to track if it's called
        mock_remote_ls_command = mocker.patch("urh.remote_ls_command")

        # Call main function
        main()

        # Verify that remote_ls_command was called with the right arguments
        mock_remote_ls_command.assert_called_once_with(
            ["ghcr.io/ublue-os/bazzite:latest"]
        )

    def test_main_remote_ls_command_with_different_registry(
        self, mocker: MockerFixture
    ):
        """Test main with remote-ls command and different registry."""
        # Mock sys.argv to simulate the remote-ls command with a different registry
        mocker.patch.object(
            sys, "argv", ["urh.py", "remote-ls", "docker.io/library/ubuntu:20.04"]
        )

        # Mock sys.exit so it doesn't actually exit
        mocker.patch("urh.sys.exit")

        # Mock the remote_ls_command to track if it's called
        mock_remote_ls_command = mocker.patch("urh.remote_ls_command")

        # Call main function
        main()

        # Verify that remote_ls_command was called with the right arguments
        mock_remote_ls_command.assert_called_once_with(
            ["docker.io/library/ubuntu:20.04"]
        )

    def test_main_remote_ls_command_no_args(self, mocker: MockerFixture):
        """Test main with remote-ls command but no arguments (should show submenu)."""
        # Mock sys.argv to simulate the remote-ls command with no arguments
        mocker.patch.object(sys, "argv", ["urh.py", "remote-ls"])

        # Mock sys.exit so it doesn't actually exit
        mocker.patch("urh.sys.exit")

        # Mock the remote_ls_command to track if it's called
        mock_remote_ls_command = mocker.patch("urh.remote_ls_command")

        # Call main function
        main()

        # Verify that remote_ls_command was called with no arguments (to show submenu)
        mock_remote_ls_command.assert_called_once_with([])
