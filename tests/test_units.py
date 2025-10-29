"""Unit tests for ublue-rebase-helper (urh.py)."""

import sys
import os
from pytest_mock import MockerFixture

# Add the parent directory to sys.path so we can import urh
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urh import (
    run_command,
    show_command_menu,
    rebase_command,
    check_command,
    ls_command,
    rollback_command,
    pin_command,
    unpin_command,
    rm_command,
    help_command,
)


class TestRunCommand:
    """Unit tests for the run_command function."""

    def test_run_command_success(self, mocker: MockerFixture):
        """Test run_command returns correct exit code when command succeeds."""
        mock_subprocess_run = mocker.patch("urh.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_subprocess_run.return_value = mock_result

        result = run_command(["echo", "hello"])
        assert result == 0
        mock_subprocess_run.assert_called_once_with(["echo", "hello"], check=False)

    def test_run_command_failure(self, mocker: MockerFixture):
        """Test run_command returns correct exit code when command fails."""
        mock_subprocess_run = mocker.patch("urh.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.returncode = 1
        mock_subprocess_run.return_value = mock_result

        result = run_command(["false"])
        assert result == 1

    def test_run_command_file_not_found(self, mocker: MockerFixture):
        """Test run_command handles FileNotFoundError."""
        mocker.patch("urh.subprocess.run", side_effect=FileNotFoundError)
        mock_print = mocker.patch("urh.print")

        result = run_command(["nonexistent-command"])
        assert result == 1
        mock_print.assert_called_once_with("Command not found: nonexistent-command")


class TestRebaseCommand:
    """Unit tests for the rebase_command function."""

    def test_rebase_command_with_url(self, mocker: MockerFixture):
        """Test rebase_command with valid URL."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        rebase_command(["some-url"])
        mock_run_command.assert_called_once_with(
            ["sudo", "rpm-ostree", "rebase", "some-url"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_rebase_command_no_args(self, mocker: MockerFixture):
        """Test rebase_command prints usage when no args provided."""
        mock_print = mocker.patch("urh.print")

        rebase_command([])
        mock_print.assert_called_once_with("Usage: urh.py rebase <url>")


class TestCheckCommand:
    """Unit tests for the check_command function."""

    def test_check_command(self, mocker: MockerFixture):
        """Test check_command executes correct command."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        check_command([])
        mock_run_command.assert_called_once_with(
            ["sudo", "rpm-ostree", "upgrade", "--check"]
        )
        mock_sys_exit.assert_called_once_with(0)


class TestLsCommand:
    """Unit tests for the ls_command function."""

    def test_ls_command(self, mocker: MockerFixture):
        """Test ls_command executes correct command."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        ls_command([])
        mock_run_command.assert_called_once_with(["rpm-ostree", "status", "-v"])
        mock_sys_exit.assert_called_once_with(0)


class TestRollbackCommand:
    """Unit tests for the rollback_command function."""

    def test_rollback_command(self, mocker: MockerFixture):
        """Test rollback_command executes correct command."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        rollback_command([])
        mock_run_command.assert_called_once_with(["sudo", "rpm-ostree", "rollback"])
        mock_sys_exit.assert_called_once_with(0)


class TestPinCommand:
    """Unit tests for the pin_command function."""

    def test_pin_command_with_number(self, mocker: MockerFixture):
        """Test pin_command with valid number."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        pin_command(["1"])
        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "pin", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_pin_command_no_args(self, mocker: MockerFixture):
        """Test pin_command prints usage when no args provided."""
        mock_print = mocker.patch("urh.print")

        pin_command([])
        mock_print.assert_called_once_with("Usage: urh.py pin <num>")

    def test_pin_command_invalid_number(self, mocker: MockerFixture):
        """Test pin_command handles invalid number."""
        mock_print = mocker.patch("urh.print")

        pin_command(["invalid"])
        mock_print.assert_called_once_with("Invalid deployment number: invalid")


class TestUnpinCommand:
    """Unit tests for the unpin_command function."""

    def test_unpin_command_with_number(self, mocker: MockerFixture):
        """Test unpin_command with valid number."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        unpin_command(["2"])
        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "pin", "-u", "2"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_unpin_command_no_args(self, mocker: MockerFixture):
        """Test unpin_command prints usage when no args provided."""
        mock_print = mocker.patch("urh.print")

        unpin_command([])
        mock_print.assert_called_once_with("Usage: urh.py unpin <num>")

    def test_unpin_command_invalid_number(self, mocker: MockerFixture):
        """Test unpin_command handles invalid number."""
        mock_print = mocker.patch("urh.print")

        unpin_command(["invalid"])
        mock_print.assert_called_once_with("Invalid deployment number: invalid")


class TestRmCommand:
    """Unit tests for the rm_command function."""

    def test_rm_command_with_number(self, mocker: MockerFixture):
        """Test rm_command with valid number."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        rm_command(["3"])
        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "cleanup", "-r", "3"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_rm_command_no_args(self, mocker: MockerFixture):
        """Test rm_command prints usage when no args provided."""
        mock_print = mocker.patch("urh.print")

        rm_command([])
        mock_print.assert_called_once_with("Usage: urh.py rm <num>")

    def test_rm_command_invalid_number(self, mocker: MockerFixture):
        """Test rm_command handles invalid number."""
        mock_print = mocker.patch("urh.print")

        rm_command(["invalid"])
        mock_print.assert_called_once_with("Invalid deployment number: invalid")


class TestHelpCommand:
    """Unit tests for the help_command function."""

    def test_help_command(self, mocker: MockerFixture):
        """Test help_command prints help information."""
        mock_print = mocker.patch("urh.print")

        help_command([])
        # Check that print was called at least once
        assert mock_print.called


class TestShowCommandMenu:
    """Unit tests for the show_command_menu function to catch gum output issues."""

    def test_show_command_menu_calls_gum_with_correct_parameters(
        self, mocker: MockerFixture
    ):
        """Test that show_command_menu calls gum with parameters that make it interactive."""
        # Mock isatty to return True to trigger gum usage
        mocker.patch("urh.os.isatty", return_value=True)

        # Mock the subprocess.run to capture how it's called
        mock_subprocess_run = mocker.patch("urh.subprocess.run")

        # Create a mock result object
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # Simulate user cancellation to avoid hanging
        mock_result.stdout = ""  # No selection
        mock_subprocess_run.return_value = mock_result

        # Call the function
        show_command_menu()

        # Verify subprocess.run was called with gum command
        assert mock_subprocess_run.called

        # Get the call args to check for proper parameters
        call_args = mock_subprocess_run.call_args
        assert call_args is not None

        # Extract the command and arguments
        args, kwargs = call_args
        cmd = args[0] if args else []

        # Check that gum command is being called
        assert "gum" in cmd
        assert "choose" in cmd

        # The critical test: ensure it's not using capture_output=True for TTY context
        # In the current broken implementation, capture_output=True prevents display
        # This test will catch the bug by checking if output was intended to be captured
        if "capture_output" in kwargs and kwargs["capture_output"]:
            assert False, (
                "gum should not use capture_output=True as it prevents output from being visible in terminal"
            )

    def test_show_command_menu_uses_stdout_for_gum_in_tty(self, mocker: MockerFixture):
        """Test that when running in TTY context, gum captures stdout to get selection."""
        # Mock isatty to return True to trigger gum usage
        mocker.patch("urh.os.isatty", return_value=True)

        # Mock the subprocess.run to capture how it's called
        mock_subprocess_run = mocker.patch("urh.subprocess.run")

        # Create a mock result object
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # Simulate user cancellation
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result

        # Call the function
        show_command_menu()

        # Get the call args
        call_args = mock_subprocess_run.call_args
        assert call_args is not None

        args, kwargs = call_args
        cmd = args[0] if args else []

        # Check that gum command is being called
        assert "gum" in cmd
        assert "choose" in cmd

        # For gum's choose command to work properly:
        # - stdout needs to be captured to receive the user selection
        # - stderr and stdin should not be redirected to allow interactive UI
        assert "stdout" in kwargs and kwargs["stdout"] is not None, (
            "stdout must be captured to receive user selection from gum"
        )
        assert "stderr" not in kwargs or kwargs.get("stderr") is None, (
            "stderr should not be redirected to allow gum interface to be visible"
        )

    def test_show_command_menu_gum_command_structure(self, mocker: MockerFixture):
        """Test the specific structure of the gum command being executed."""
        # Mock isatty to return True to trigger gum usage
        mocker.patch("urh.os.isatty", return_value=True)

        # Mock the subprocess.run to capture how it's called
        mock_subprocess_run = mocker.patch("urh.subprocess.run")

        # Create a mock result object
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # User cancellation
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result

        # Call the function
        show_command_menu()

        # Get the call args to examine the command structure
        call_args = mock_subprocess_run.call_args
        assert call_args is not None

        args, kwargs = call_args
        cmd = args[0] if args else []

        # Verify the command structure
        assert cmd[0] == "gum"
        assert cmd[1] == "choose"

        # Check for the specific UI enhancements we expect
        assert "--cursor" in cmd
        assert "→" in cmd
        assert "--selected-prefix" in cmd
        assert "✓ " in cmd

        # Check that the commands we want to show are in the command list
        expected_commands = [
            "rebase - Rebase to a container image",
            "check - Check for available updates",
            "ls - List deployments with details",
        ]

        for expected_cmd in expected_commands:
            assert expected_cmd in cmd, (
                f"Expected command '{expected_cmd}' not found in gum command"
            )

    def test_show_command_menu_handles_no_selection(self, mocker: MockerFixture):
        """Test behavior when no command is selected in gum."""
        # Mock isatty to return True to trigger gum usage
        mocker.patch("urh.os.isatty", return_value=True)

        # Mock subprocess.run to simulate user not making a selection
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # Gum exits with 1 when no selection is made
        mock_result.stdout = ""  # No output when no selection
        mocker.patch("urh.subprocess.run", return_value=mock_result)

        # Mock print to capture output
        mock_print = mocker.patch("urh.print")

        result = show_command_menu()

        # When gum returns non-zero exit code (no selection), it should return "help"
        assert result == "help"
        # And should print a message about no command being selected
        mock_print.assert_called_with("No command selected.")
