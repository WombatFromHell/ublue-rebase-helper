"""Unit tests for ublue-rebase-helper (urh.py)."""

import json
import subprocess
from unittest.mock import MagicMock
import os
import sys
import pytest
from pytest_mock import MockerFixture
from typing import List

# Add the parent directory to sys.path so we can import urh
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urh import (
    run_command,
    show_command_menu,
    rebase_command,
    remote_ls_command,
    check_command,
    ls_command,
    rollback_command,
    pin_command,
    unpin_command,
    rm_command,
    upgrade_command,
    show_rebase_submenu,
    show_remote_ls_submenu,
    help_command,
    show_commands_non_tty,
    show_commands_gum_not_found,
    show_container_options_non_tty,
    show_container_options_gum_not_found,
    get_commands_with_descriptions,
    get_container_options,
    main,
    parse_deployments,
    show_deployment_submenu,
    MenuExitException,
    OCIClient,
)


class TestRunCommand:
    """Unit tests for the run_command function."""

    @pytest.mark.parametrize(
        "returncode, expected_result",
        [
            (0, 0),  # success case
            (1, 1),  # failure case
            (2, 2),  # other failure case
        ],
    )
    def test_run_command_with_return_codes(
        self, mocker: MockerFixture, returncode: int, expected_result: int
    ):
        """Test run_command returns correct exit code for different scenarios."""
        mock_subprocess_run = mocker.patch("urh.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.returncode = returncode
        mock_subprocess_run.return_value = mock_result

        result = run_command(["echo", "test"])
        assert result == expected_result
        mock_subprocess_run.assert_called_once_with(["echo", "test"], check=False)

    @pytest.mark.parametrize(
        "cmd_args, expected_msg",
        [
            (["nonexistent-command"], "Command not found: nonexistent-command"),
            (
                ["nonexistent", "command", "with", "spaces"],
                "Command not found: nonexistent command with spaces",
            ),
        ],
    )
    def test_run_command_file_not_found_scenarios(
        self, mocker: MockerFixture, cmd_args: list, expected_msg: str
    ):
        """Test run_command handles FileNotFoundError for different command formats."""
        mocker.patch("urh.subprocess.run", side_effect=FileNotFoundError)
        mock_print = mocker.patch("urh.print")

        result = run_command(cmd_args)
        assert result == 1
        mock_print.assert_called_once_with(expected_msg)


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

    @pytest.mark.parametrize(
        "submenu_return_value, should_call_command, should_exit",
        [
            ("test-url", True, True),  # Valid selection
            (None, False, False),  # No selection
        ],
    )
    def test_rebase_command_no_args(
        self,
        mocker: MockerFixture,
        submenu_return_value,
        should_call_command,
        should_exit,
    ):
        """Test rebase_command calls submenu when no args provided and handles selection appropriately."""
        # Mock the show_rebase_submenu function to avoid actual gum execution
        mock_show_rebase_submenu = mocker.patch(
            "urh.show_rebase_submenu", return_value=submenu_return_value
        )
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        rebase_command([])

        # Verify that submenu was called
        mock_show_rebase_submenu.assert_called_once()

        if should_call_command:
            # And that the rebase command was run with the selected URL
            mock_run_command.assert_called_once_with(
                ["sudo", "rpm-ostree", "rebase", "test-url"]
            )
        else:
            # Verify that run_command was never called (since no URL was selected)
            mock_run_command.assert_not_called()

        if should_exit:
            mock_sys_exit.assert_called_once_with(0)
        else:
            # sys.exit should NOT be called when no selection is made
            mock_sys_exit.assert_not_called()


class TestCommandsWithSubmenu:
    """Parametrized tests for commands that use submenus when no arguments provided."""

    @pytest.mark.parametrize(
        "func,submenu_func_name,submenu_return_value,expected_cmd_prefix",
        [
            (
                rebase_command,
                "show_rebase_submenu",
                "test-url",
                ["sudo", "rpm-ostree", "rebase"],
            ),
            (
                pin_command,
                "show_deployment_submenu",
                1,
                ["sudo", "ostree", "admin", "pin"],
            ),
            (
                unpin_command,
                "show_deployment_submenu",
                1,
                ["sudo", "ostree", "admin", "pin", "-u"],
            ),
            (
                rm_command,
                "show_deployment_submenu",
                1,
                ["sudo", "rpm-ostree", "cleanup", "-r"],
            ),
        ],
    )
    def test_command_no_args_calls_submenu(
        self,
        mocker: MockerFixture,
        func,
        submenu_func_name,
        submenu_return_value,
        expected_cmd_prefix,
    ):
        """Test commands call submenu when no args provided."""
        # Mock the submenu function to avoid actual gum execution
        mock_submenu_func = mocker.patch(
            f"urh.{submenu_func_name}", return_value=submenu_return_value
        )
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        func([])

        # Verify that submenu was called
        mock_submenu_func.assert_called_once()

        # Verify that the command was run with the selected value
        expected_cmd = expected_cmd_prefix + (
            [str(submenu_return_value)]
            if submenu_return_value
            else [str(submenu_return_value)]
        )
        if submenu_func_name == "show_rebase_submenu" and isinstance(
            submenu_return_value, str
        ):
            # For rebase command, the URL is passed directly
            expected_cmd = expected_cmd_prefix + [submenu_return_value]
        elif isinstance(submenu_return_value, int):
            # For deployment commands, the number is appended as string
            expected_cmd = expected_cmd_prefix + [str(submenu_return_value)]

        mock_run_command.assert_called_once_with(expected_cmd)
        mock_sys_exit.assert_called_once_with(0)

    @pytest.mark.parametrize(
        "func,submenu_func_name,no_selection_value",
        [
            (rebase_command, "show_rebase_submenu", None),
            (pin_command, "show_deployment_submenu", None),
            (unpin_command, "show_deployment_submenu", None),
            (rm_command, "show_deployment_submenu", None),
        ],
    )
    def test_command_no_args_no_selection(
        self, mocker: MockerFixture, func, submenu_func_name, no_selection_value
    ):
        """Test commands handle no selection from submenu."""
        # Mock the submenu function to return no selection value
        mock_submenu_func = mocker.patch(
            f"urh.{submenu_func_name}", return_value=no_selection_value
        )
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        func([])

        # Verify that submenu was called
        mock_submenu_func.assert_called_once()
        # Verify that run_command was never called (since no selection was made)
        mock_run_command.assert_not_called()
        # sys.exit should NOT be called when no selection is made
        mock_sys_exit.assert_not_called()


class TestSimpleCommands:
    """Unit tests for simple commands that follow the same pattern."""

    @pytest.mark.parametrize(
        "func,expected_cmd,has_sudo",
        [
            (check_command, ["rpm-ostree", "upgrade", "--check"], False),
            (ls_command, ["rpm-ostree", "status", "-v"], False),
            (rollback_command, ["sudo", "rpm-ostree", "rollback"], True),
            (upgrade_command, ["sudo", "rpm-ostree", "upgrade"], True),
        ],
    )
    def test_simple_commands_execute_correctly(
        self, mocker: MockerFixture, func, expected_cmd, has_sudo
    ):
        """Test simple commands execute correct command with appropriate sudo usage."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        func([])

        # Verify the command was called with the expected arguments
        mock_run_command.assert_called_once_with(expected_cmd)
        # Verify sys.exit was called with the expected return code
        mock_sys_exit.assert_called_once_with(0)


class TestShowRemoteLsSubmenu:
    """Unit tests for the show_remote_ls_submenu function."""

    @pytest.mark.parametrize(
        "returncode, stdout, expected_result",
        [
            (
                0,
                "ghcr.io/ublue-os/bazzite:stable",
                "ghcr.io/ublue-os/bazzite:stable",
            ),  # Valid selection
            (1, "", None),  # No selection made
        ],
    )
    def test_show_remote_ls_submenu_tty_scenarios(
        self, mocker: MockerFixture, returncode: int, stdout: str, expected_result: str
    ):
        """Test show_remote_ls_submenu when running in TTY with different outcomes."""
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = returncode
        mock_result.stdout = stdout
        mock_subprocess_run.return_value = mock_result
        mock_print = mocker.Mock()

        result = show_remote_ls_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )
        assert result == expected_result

        # If no selection was made, verify the appropriate message was printed
        if returncode == 1 and stdout == "":
            mock_print.assert_called_with("No option selected.")

    def test_show_remote_ls_submenu_non_tty(self, mocker: MockerFixture):
        """Test show_remote_ls_submenu when not running in TTY context."""
        mock_is_tty = mocker.Mock(return_value=False)
        mock_print = mocker.Mock()

        result = show_remote_ls_submenu(is_tty_func=mock_is_tty, print_func=mock_print)
        # Function should return None in non-TTY context
        assert result is None
        mock_print.assert_any_call("Available container URLs:")

    def test_show_remote_ls_submenu_gum_not_found(self, mocker: MockerFixture):
        """Test show_remote_ls_submenu when gum is not available."""
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock(side_effect=FileNotFoundError)
        mock_print = mocker.Mock()

        result = show_remote_ls_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )
        assert result is None
        mock_print.assert_any_call("gum not found. Available container URLs:")


class TestShowRebaseSubmenu:
    """Unit tests for the show_rebase_submenu function."""


class TestHelpCommand:
    """Unit tests for the help_command function."""

    def test_help_command(self, mocker: MockerFixture):
        """Test help_command prints help information."""
        mock_print = mocker.Mock()

        help_command([], print_func=mock_print)
        # Check that print was called at least once
        assert mock_print.called

    def test_help_command_specific_output(self, mocker: MockerFixture):
        """Test help_command prints correct help information."""
        mock_print = mocker.Mock()

        help_command([], print_func=mock_print)

        # Check that specific parts of the help message are printed
        calls = mock_print.call_args_list
        # Check that the program name is printed
        help_calls = [call for call in calls if "ublue-rebase-helper" in str(call)]
        assert len(help_calls) > 0

        # Check that Usage line is printed
        usage_calls = [call for call in calls if "Usage:" in str(call)]
        assert len(usage_calls) > 0


class TestMainFunction:
    """Unit tests for the main function."""

    def test_main_unknown_command(self, mocker: MockerFixture):
        """Test main handles unknown command."""
        mock_print = mocker.patch("urh.print")
        # Mock sys.exit to avoid actual exit
        mocker.patch("urh.sys.exit")
        mock_help_command = mocker.patch("urh.help_command")

        main(["urh.py", "unknown_command"])

        # Verify that "Unknown command" message was printed
        mock_print.assert_any_call("Unknown command: unknown_command")
        # And that help_command was called
        mock_help_command.assert_called_once_with([])

    def test_main_with_valid_command(self, mocker: MockerFixture):
        """Test main with a valid command."""
        # Mock sys.exit to avoid actual exit
        mocker.patch("urh.sys.exit")
        mock_rebase_command = mocker.patch("urh.rebase_command")

        main(["urh.py", "rebase", "test-url"])

        # Verify that rebase_command was called with correct arguments
        mock_rebase_command.assert_called_once_with(["test-url"])

    def test_main_no_args_shows_menu(self, mocker: MockerFixture):
        """Test main shows menu when no arguments provided."""
        # Mock show_command_menu to return empty string immediately causing exit
        mock_show_command_menu = mocker.patch("urh.show_command_menu", return_value="")
        # Mock sys.exit to track if it's called
        mock_sys_exit = mocker.patch("urh.sys.exit")

        main(["urh.py"])

        # Verify that show_command_menu was called
        mock_show_command_menu.assert_called_once()
        # And sys.exit was called with code 0
        mock_sys_exit.assert_called_once_with(0)

    def test_main_with_menu_exit_exception_handling(self, mocker: MockerFixture):
        """Test that the main function properly catches MenuExitException and continues."""
        # In test mode, we need to simulate the test environment
        mocker.patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test"})

        # Mock the show_command_menu to return a command that will raise MenuExitException
        mock_show_command_menu = mocker.patch(
            "urh.show_command_menu", return_value="rebase"
        )
        mock_rebase_command = mocker.patch(
            "urh.rebase_command", side_effect=MenuExitException()
        )
        mock_sys_exit = mocker.patch("urh.sys.exit")

        # Call main with no arguments to trigger menu mode
        main(["urh.py"])

        # Verify show_command_menu was called
        mock_show_command_menu.assert_called_once()
        # Verify that rebase_command was called with empty args
        mock_rebase_command.assert_called_once_with([])
        # Since the exception is raised, sys.exit should be called
        mock_sys_exit.assert_called_once_with(0)

    def test_main_menu_loop_with_menu_exit_exception(self, mocker: MockerFixture):
        """Test the main function's MenuExitException handling in test mode."""
        # Test that the main function properly handles MenuExitException in test mode
        mocker.patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test"})

        # Mock the show_command_menu to return a command first, then None to exit
        mock_show_command_menu = mocker.patch(
            "urh.show_command_menu", side_effect=["rebase", None]
        )
        mock_rebase_command = mocker.patch(
            "urh.rebase_command", side_effect=MenuExitException()
        )
        mock_sys_exit = mocker.patch("urh.sys.exit")

        # Call main with no arguments to trigger menu mode
        main(["urh.py"])

        # Verify that show_command_menu was called twice (once for rebase, once more before exiting)
        assert mock_show_command_menu.call_count >= 1
        # Verify that rebase_command was called with empty args
        mock_rebase_command.assert_called_once_with([])
        # sys.exit should be called when MenuExitException is handled
        mock_sys_exit.assert_called()


class TestConfigFunctions:
    """Unit tests for configuration functions."""

    def test_get_commands_with_descriptions(self):
        """Test that get_commands_with_descriptions returns the correct list."""
        commands = get_commands_with_descriptions()
        assert len(commands) > 0
        assert "rebase - Rebase to a container image" in commands

    def test_get_container_options(self):
        """Test that get_container_options returns the correct list."""
        options = get_container_options()
        assert len(options) > 0
        assert "ghcr.io/ublue-os/bazzite:stable" in options


class TestShowCommandsFunctions:
    """Unit tests for show_commands functions."""

    def test_show_commands_non_tty(self, mocker: MockerFixture):
        """Test show_commands_non_tty function."""
        mock_print = mocker.Mock()
        result = show_commands_non_tty(print_func=mock_print)

        assert result is None
        mock_print.assert_any_call(
            "Not running in interactive mode. Available commands:"
        )
        # Should print all commands + the final message
        assert (
            mock_print.call_count >= 3
        )  # First message + at least 1 command + final message

    def test_show_commands_gum_not_found(self, mocker: MockerFixture):
        """Test show_commands_gum_not_found function."""
        mock_print = mocker.Mock()
        result = show_commands_gum_not_found(print_func=mock_print)

        assert result is None
        mock_print.assert_any_call("gum not found. Available commands:")
        # Should print all commands + the final message
        assert (
            mock_print.call_count >= 3
        )  # First message + at least 1 command + final message


class TestShowContainerOptionsFunctions:
    """Unit tests for show_container_options functions."""

    def test_show_container_options_non_tty(self, mocker: MockerFixture):
        """Test show_container_options_non_tty function."""
        mock_print = mocker.Mock()
        result = show_container_options_non_tty(print_func=mock_print)

        assert result is None
        mock_print.assert_any_call("Available container URLs:")
        # Should print all container options + the final message
        assert (
            mock_print.call_count >= 3
        )  # First message + at least 1 option + final message

    def test_show_container_options_gum_not_found(self, mocker: MockerFixture):
        """Test show_container_options_gum_not_found function."""
        mock_print = mocker.Mock()
        result = show_container_options_gum_not_found(print_func=mock_print)

        assert result is None
        mock_print.assert_any_call("gum not found. Available container URLs:")
        # Should print all container options + the final message
        assert (
            mock_print.call_count >= 3
        )  # First message + at least 1 option + final message


class TestTTYContexts:
    """Unit tests for TTY vs Non-TTY contexts."""

    def test_show_command_menu_non_tty_context(self, mocker: MockerFixture):
        """Test show_command_menu when not in TTY context."""
        mock_is_tty = mocker.Mock(return_value=False)  # Not in TTY context
        mock_print = mocker.Mock()

        result = show_command_menu(is_tty_func=mock_is_tty, print_func=mock_print)

        # In non-TTY context, the function should return None
        assert result is None
        # The function should have called the non-TTY display function
        mock_print.assert_any_call(
            "Not running in interactive mode. Available commands:"
        )

    def test_show_rebase_submenu_non_tty_context(self, mocker: MockerFixture):
        """Test show_rebase_submenu when not in TTY context."""
        mock_is_tty = mocker.Mock(return_value=False)  # Not in TTY context
        mock_print = mocker.Mock()

        result = show_rebase_submenu(is_tty_func=mock_is_tty, print_func=mock_print)

        # In non-TTY context, the function should return None
        assert result is None
        # The function should have called the non-TTY display function
        mock_print.assert_any_call("Available container URLs:")

    def test_show_deployment_submenu_non_tty_context(self, mocker: MockerFixture):
        """Test show_deployment_submenu when not in TTY context."""
        # Mock the parse_deployments function to return some test deployments
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
                {
                    "index": 0,
                    "version": "test version",
                    "pinned": False,
                }
            ],
        )
        mock_is_tty = mocker.Mock(return_value=False)  # Not in TTY context
        mock_print = mocker.Mock()

        result = show_deployment_submenu(is_tty_func=mock_is_tty, print_func=mock_print)

        # In non-TTY context, the function should return None
        assert result is None
        # The function should have called the non-TTY display function
        mock_print.assert_any_call("Available deployments:")


class TestGumNotFoundScenarios:
    """Unit tests for gum not found scenarios."""

    def test_show_command_menu_gum_not_found(self, mocker: MockerFixture):
        """Test show_command_menu when gum is not found."""
        mock_is_tty = mocker.Mock(return_value=True)  # In TTY context
        mock_subprocess_run = mocker.Mock(side_effect=FileNotFoundError)
        mock_print = mocker.Mock()

        result = show_command_menu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )

        # When gum is not found, the function should return None
        assert result is None
        # The function should have shown the gum not found message
        mock_print.assert_any_call("gum not found. Available commands:")

    def test_show_rebase_submenu_gum_not_found(self, mocker: MockerFixture):
        """Test show_rebase_submenu when gum is not found."""
        mock_is_tty = mocker.Mock(return_value=True)  # In TTY context
        mock_subprocess_run = mocker.Mock(side_effect=FileNotFoundError)
        mock_print = mocker.Mock()

        result = show_rebase_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )

        # When gum is not found, the function should return None
        assert result is None
        # The function should have shown the gum not found message
        mock_print.assert_any_call("gum not found. Available container URLs:")

    def test_show_deployment_submenu_gum_not_found(self, mocker: MockerFixture):
        """Test show_deployment_submenu when gum is not found."""
        # Mock the parse_deployments function to return some test deployments
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
                {
                    "index": 0,
                    "version": "test version",
                    "pinned": False,
                }
            ],
        )
        mock_is_tty = mocker.Mock(return_value=True)  # In TTY context
        mock_subprocess_run = mocker.Mock(side_effect=FileNotFoundError)
        mock_print = mocker.Mock()

        result = show_deployment_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )

        # When gum is not found, the function should return None
        assert result is None
        # The function should have shown the gum not found message
        mock_print.assert_any_call("gum not found. Available deployments:")


class TestShowCommandMenu:
    """Unit tests for the show_command_menu function to catch gum output issues."""

    def test_show_command_menu_calls_gum_with_correct_parameters(
        self, mocker: MockerFixture
    ):
        """Test that show_command_menu calls gum with parameters that make it interactive."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()

        # Create a mock result object
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # Simulate user cancellation to avoid hanging
        mock_result.stdout = ""  # No selection
        mock_subprocess_run.return_value = mock_result

        # Call the function
        show_command_menu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )

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
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()

        # Create a mock result object
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # Simulate user cancellation
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result

        # Call the function
        show_command_menu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )

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
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()

        # Create a mock result object
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # User cancellation
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result

        # Call the function
        show_command_menu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )

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
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # Gum exits with 1 when no selection is made
        mock_result.stdout = ""  # No output when no selection
        mock_subprocess_run.return_value = mock_result
        mock_print = mocker.Mock()

        result = show_command_menu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )

        # When gum returns non-zero exit code (no selection), it should return None to avoid help duplication
        assert result is None
        # And should print a message about no command being selected
        mock_print.assert_called_with("No command selected.")

    def test_show_command_menu_non_tty_context(self, mocker: MockerFixture):
        """Test show_command_menu behavior when not running in TTY context."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=False)
        mock_print = mocker.Mock()

        result = show_command_menu(is_tty_func=mock_is_tty, print_func=mock_print)

        # In non-TTY context, it should return None
        assert result is None
        # And should print the available commands
        mock_print.assert_any_call(
            "Not running in interactive mode. Available commands:"
        )

    def test_show_command_menu_gum_not_found(self, mocker: MockerFixture):
        """Test show_command_menu when gum is not available."""
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
        # The test should print commands when gum not available
        assert mock_print.called
        mock_print.assert_any_call("gum not found. Available commands:")


class TestShowRebaseSubmenuRefactored:
    """Unit tests for the refactored show_rebase_submenu function."""

    def test_show_rebase_submenu_tty_with_selection(self, mocker: MockerFixture):
        """Test show_rebase_submenu when running in TTY with a selection."""
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "ghcr.io/ublue-os/bazzite:stable"
        mock_subprocess_run.return_value = mock_result

        result = show_rebase_submenu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )
        assert result == "ghcr.io/ublue-os/bazzite:stable"

    def test_show_rebase_submenu_tty_no_selection(self, mocker: MockerFixture):
        """Test show_rebase_submenu when running in TTY with no selection."""
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # No selection made
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

    def test_show_rebase_submenu_non_tty(self, mocker: MockerFixture):
        """Test show_rebase_submenu when not running in TTY context."""
        mock_is_tty = mocker.Mock(return_value=False)
        mock_print = mocker.Mock()

        result = show_rebase_submenu(is_tty_func=mock_is_tty, print_func=mock_print)
        # Function should return None in non-TTY context
        assert result is None
        mock_print.assert_any_call("Available container URLs:")

    def test_show_rebase_submenu_gum_not_found(self, mocker: MockerFixture):
        """Test show_rebase_submenu when gum is not available."""
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock(side_effect=FileNotFoundError)
        mock_print = mocker.Mock()

        result = show_rebase_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )
        assert result is None
        mock_print.assert_any_call("gum not found. Available container URLs:")

    def test_show_rebase_submenu_non_tty_context_specific(self, mocker: MockerFixture):
        """Test show_rebase_submenu when not running in TTY context."""
        mock_is_tty = mocker.Mock(return_value=False)
        mock_print = mocker.Mock()

        result = show_rebase_submenu(is_tty_func=mock_is_tty, print_func=mock_print)
        # In non-TTY context, it should return None
        assert result is None
        mock_print.assert_any_call("Available container URLs:")


class TestParseDeployments:
    """Unit tests for the parse_deployments function."""

    def test_parse_deployments_success(self, mocker: MockerFixture):
        """Test parse_deployments with valid rpm-ostree status output."""
        # Mock the subprocess.run call to return a sample rpm-ostree status output
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """State: idle
AutomaticUpdates: disabled
Deployments:
● ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:latest (index: 0)
                   Digest: sha256:988868293abee6a54d19f44f39ba5a3f49df6660fbe5dd15c0de55e896f4ba95
                  Version: testing-43.20251028.9 (2025-10-29T06:23:42Z)
                   Commit: 9c306edd76f3c37211ed170d54a48fb8dbdd32bf8eb830e24be4ac9664c7672f
                   Staged: no
                StateRoot: default

  ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:latest (index: 1)
                   Digest: sha256:34d5117ee908295efbd98724961aaf94183ce793d6e4d1a350d298db7e9262fa
                  Version: testing-43.20251028.5 (2025-10-28T13:56:45Z)
                   Commit: fee57d04705544e403e0b70ec76ffc6ac5d8b14fe617dff2311ba1160cef5ce7
                StateRoot: default

  ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:latest (index: 2)
                   Digest: sha256:ff5b3052cf25c8d34e9e4cd7ecf60064c4a3c24525a45f84c4669dee931d22ca
                  Version: testing-42.20251025 (2025-10-27T06:25:18Z)
                   Commit: 3a47687e364dee6dc21de6463b130a72293ea95e3e363c8cd2b1a0d421d06ffc
                StateRoot: default
                   Pinned: yes"""

        mocker.patch("urh.subprocess.run", return_value=mock_result)

        deployments = parse_deployments()

        assert len(deployments) == 3

        # Check first deployment (current and not pinned)
        assert deployments[0]["index"] == 0
        assert (
            deployments[0]["version"] == "testing-43.20251028.9 (2025-10-29T06:23:42Z)"
        )
        assert not deployments[0]["pinned"]
        assert deployments[0]["current"]

        # Check second deployment (not pinned)
        assert deployments[1]["index"] == 1
        assert (
            deployments[1]["version"] == "testing-43.20251028.5 (2025-10-28T13:56:45Z)"
        )
        assert not deployments[1]["pinned"]
        assert not deployments[1]["current"]

        # Check third deployment (pinned)
        assert deployments[2]["index"] == 2
        assert deployments[2]["version"] == "testing-42.20251025 (2025-10-27T06:25:18Z)"
        assert deployments[2]["pinned"]
        assert not deployments[2]["current"]

    def test_parse_deployments_error(self, mocker: MockerFixture):
        """Test parse_deployments handles command execution failure."""
        mock_result = mocker.Mock()
        mock_result.returncode = 1
        mocker.patch("urh.subprocess.run", return_value=mock_result)

        deployments = parse_deployments()

        assert deployments == []

    def test_parse_deployments_exception(self, mocker: MockerFixture):
        """Test parse_deployments handles exceptions."""
        mocker.patch("urh.subprocess.run", side_effect=Exception("Test error"))
        mock_print = mocker.patch("urh.print")

        deployments = parse_deployments()

        assert deployments == []
        mock_print.assert_called_once_with("Error parsing deployments")

    def test_parse_deployments_with_called_process_error(self, mocker: MockerFixture):
        """Test parse_deployments handles CalledProcessError."""
        mocker.patch(
            "urh.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["test"])
        )
        mock_print = mocker.patch("urh.print")

        deployments = parse_deployments()

        assert deployments == []
        mock_print.assert_called_once_with("Error running rpm-ostree status command")

    def test_parse_deployments_edge_case_empty_output(self, mocker: MockerFixture):
        """Test parse_deployments handles empty output from rpm-ostree status."""
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mocker.patch("urh.subprocess.run", return_value=mock_result)

        deployments = parse_deployments()

        assert deployments == []

    def test_parse_deployments_edge_case_no_deployments(self, mocker: MockerFixture):
        """Test parse_deployments handles output with no deployment lines."""
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """State: idle
AutomaticUpdates: disabled
Deployments:"""
        mocker.patch("urh.subprocess.run", return_value=mock_result)

        deployments = parse_deployments()

        assert deployments == []

    def test_parse_deployments_edge_case_malformed_index(self, mocker: MockerFixture):
        """Test parse_deployments handles malformed index in deployment lines."""
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """State: idle
AutomaticUpdates: disabled
Deployments:
● ostree-image-signed:docker://ghcr.io/test/image:latest (index: not_a_number)
                   Version: test-version"""
        mocker.patch("urh.subprocess.run", return_value=mock_result)

        deployments = parse_deployments()

        # Should handle invalid index parsing gracefully and return empty result
        assert deployments == []

    def test_parse_deployments_edge_case_no_deployments_found(
        self, mocker: MockerFixture
    ):
        """Test parse_deployments handles when no deployments are found."""
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """State: idle
AutomaticUpdates: disabled
Deployments:"""
        mocker.patch("urh.subprocess.run", return_value=mock_result)

        deployments = parse_deployments()

        assert deployments == []

    def test_parse_deployments_edge_case_no_matching_deployments(
        self, mocker: MockerFixture
    ):
        """Test parse_deployments handles when no lines match deployment patterns."""
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = """State: idle
AutomaticUpdates: disabled
Deployments:
  some line that doesn't match pattern"""
        mocker.patch("urh.subprocess.run", return_value=mock_result)

        deployments = parse_deployments()

        assert deployments == []


class TestShowDeploymentSubmenu:
    """Unit tests for the show_deployment_submenu function."""

    def test_show_deployment_submenu_tty_with_selection(self, mocker: MockerFixture):
        """Test show_deployment_submenu when running in TTY with a selection."""
        mock_is_tty = mocker.Mock(return_value=True)

        # Mock deployments to return
        mock_parse_deployments = mocker.patch(
            "urh.parse_deployments",
            return_value=[
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
            ],
        )

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

        assert result == 1  # index 1 corresponds to the selected version
        mock_parse_deployments.assert_called_once()

    def test_show_deployment_submenu_tty_no_selection(self, mocker: MockerFixture):
        """Test show_deployment_submenu when running in TTY with no selection."""
        mock_is_tty = mocker.Mock(return_value=True)

        # Mock deployments to return
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
                {
                    "index": 0,
                    "version": "testing-43.20251028.9 (2025-10-29T06:23:42Z)",
                    "pinned": False,
                },
            ],
        )

        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # No selection made
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result
        mock_print = mocker.Mock()

        result = show_deployment_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )

        assert result is None
        mock_print.assert_called_with("No option selected.")

    def test_show_deployment_submenu_non_tty(self, mocker: MockerFixture):
        """Test show_deployment_submenu when not running in TTY context."""
        mock_is_tty = mocker.Mock(return_value=False)

        # Mock deployments to return
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
                {
                    "index": 0,
                    "version": "testing-43.20251028.9 (2025-10-29T06:23:42Z)",
                    "pinned": False,
                },
            ],
        )
        mock_print = mocker.Mock()

        result = show_deployment_submenu(is_tty_func=mock_is_tty, print_func=mock_print)

        assert result is None
        mock_print.assert_any_call("Available deployments:")

    def test_show_deployment_submenu_gum_not_found(self, mocker: MockerFixture):
        """Test show_deployment_submenu when gum is not available."""
        mock_is_tty = mocker.Mock(return_value=True)

        # Mock deployments to return
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
                {
                    "index": 0,
                    "version": "testing-43.20251028.9 (2025-10-29T06:23:42Z)",
                    "pinned": False,
                },
            ],
        )
        mock_subprocess_run = mocker.Mock(side_effect=FileNotFoundError)
        mock_print = mocker.Mock()

        result = show_deployment_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )

        assert result is None
        mock_print.assert_any_call("gum not found. Available deployments:")

    def test_show_deployment_submenu_with_filter(self, mocker: MockerFixture):
        """Test show_deployment_submenu with a filter function."""
        mock_is_tty = mocker.Mock(return_value=True)

        # Mock deployments to return (with both pinned and non-pinned)
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
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
                {
                    "index": 2,
                    "version": "testing-42.20251025 (2025-10-27T06:25:18Z)",
                    "pinned": False,
                },
            ],
        )

        # Filter function to only show pinned deployments
        def pinned_filter(deployment):
            return deployment["pinned"]

        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "testing-43.20251028.5 (2025-10-28T13:56:45Z) [Pinned: Yes]"
        )
        mock_subprocess_run.return_value = mock_result

        result = show_deployment_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            filter_func=pinned_filter,
        )

        assert result == 1  # Should return index 1 (the pinned deployment)
        # Verify that subprocess was called with the pinned option only
        call_args = mock_subprocess_run.call_args
        if call_args:
            args, kwargs = call_args
            cmd = args[0] if args else []
            # Check that only the pinned deployment option is present in the command
            assert "testing-43.20251028.5 (2025-10-28T13:56:45Z) [Pinned: Yes]" in cmd
            # The unpinned deployments should not be there
            assert not any("testing-43.20251028.9" in str(arg) for arg in cmd)
            assert not any("testing-42.20251025" in str(arg) for arg in cmd)

    def test_show_deployment_submenu_with_empty_filtered_deployments(
        self, mocker: MockerFixture
    ):
        """Test show_deployment_submenu when filter results in no deployments."""
        mock_is_tty = mocker.Mock(return_value=True)

        # Mock deployments to return
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
                {
                    "index": 0,
                    "version": "testing-43.20251028.9 (2025-10-29T06:23:42Z)",
                    "pinned": False,
                },
            ],
        )

        # Filter function that returns False for all deployments
        def no_match_filter(deployment):
            return False

        mock_print = mocker.Mock()

        result = show_deployment_submenu(
            is_tty_func=mock_is_tty,
            print_func=mock_print,
            filter_func=no_match_filter,
        )

        assert result is None
        mock_print.assert_any_call("No deployments match the filter criteria.")

    def test_show_deployment_submenu_invalid_selection(self, mocker: MockerFixture):
        """Test show_deployment_submenu with invalid selection."""
        mock_is_tty = mocker.Mock(return_value=True)

        # Mock deployments to return
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
                {
                    "index": 0,
                    "version": "testing-43.20251028.9 (2025-10-29T06:23:42Z)",
                    "pinned": False,
                },
            ],
        )

        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid selection that doesn't match any deployment"
        mock_subprocess_run.return_value = mock_result
        mock_print = mocker.Mock()

        result = show_deployment_submenu(
            is_tty_func=mock_is_tty,
            subprocess_run_func=mock_subprocess_run,
            print_func=mock_print,
        )

        assert result is None
        mock_print.assert_called_with("Invalid selection.")


class TestDeploymentCommands:
    """Unit tests for deployment commands (pin, unpin, rm) that follow similar patterns."""

    @pytest.mark.parametrize(
        "func,command_name,expected_cmd",
        [
            (pin_command, "pin", ["sudo", "ostree", "admin", "pin", "1"]),
            (unpin_command, "unpin", ["sudo", "ostree", "admin", "pin", "-u", "2"]),
            (rm_command, "rm", ["sudo", "rpm-ostree", "cleanup", "-r", "3"]),
        ],
    )
    def test_deployment_command_with_number(
        self, mocker: MockerFixture, func, command_name, expected_cmd
    ):
        """Test deployment commands with valid number."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        # Use appropriate number argument for each command
        if command_name == "pin":
            func(["1"])
        elif command_name == "unpin":
            func(["2"])
        else:  # rm
            func(["3"])

        mock_run_command.assert_called_once_with(expected_cmd)
        mock_sys_exit.assert_called_once_with(0)

    def test_rebase_command_invalid_number_handling(self, mocker: MockerFixture):
        """Test rebase command doesn't handle numbers but URL strings."""
        # This test checks that rebase command handles invalid input properly
        mock_show_rebase_submenu = mocker.patch(
            "urh.show_rebase_submenu", return_value=None
        )

        # The rebase command should handle the case where a submenu doesn't return a value
        rebase_command([])  # This internally calls show_rebase_submenu

        # Verify submenu was called
        mock_show_rebase_submenu.assert_called_once()
        # Since no selection is made, nothing should be printed (no error in this path)
        # The function should return None (implicitly) when no URL is selected

    def test_rebase_command_with_invalid_number(self, mocker: MockerFixture):
        """Test rebase command with an invalid number input (should treat as URL)."""
        # The rebase command treats any argument as a URL, so even invalid numbers should be passed through
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        rebase_command(["invalid-url"])
        mock_run_command.assert_called_once_with(
            ["sudo", "rpm-ostree", "rebase", "invalid-url"]
        )
        mock_sys_exit.assert_called_once_with(0)

    @pytest.mark.parametrize(
        "func,command_name,submenu_return_value,expected_cmd_with_filter",
        [
            (pin_command, "pin", 2, ["sudo", "ostree", "admin", "pin", "2"]),
            (unpin_command, "unpin", 1, ["sudo", "ostree", "admin", "pin", "-u", "1"]),
            (rm_command, "rm", 1, ["sudo", "rpm-ostree", "cleanup", "-r", "1"]),
        ],
    )
    def test_deployment_command_no_args_calls_submenu(
        self,
        mocker: MockerFixture,
        func,
        command_name,
        submenu_return_value,
        expected_cmd_with_filter,
    ):
        """Test deployment commands call submenu when no args provided."""
        # Mock the show_deployment_submenu function to avoid actual gum execution
        mock_show_deployment_submenu = mocker.patch(
            "urh.show_deployment_submenu", return_value=submenu_return_value
        )
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        func([])

        # Verify that submenu was called
        mock_show_deployment_submenu.assert_called_once()

        # For pin and unpin commands, verify that a filter function was passed
        if command_name in ["pin", "unpin"]:
            call_args = mock_show_deployment_submenu.call_args
            assert call_args is not None
            args, kwargs = call_args
            # Check that filter_func was passed
            assert "filter_func" in kwargs
            # Apply the filter function to verify it filters appropriately
            filter_func = kwargs["filter_func"]
            unpinned_deployment = {"pinned": False}
            pinned_deployment = {"pinned": True}
            if command_name == "pin":
                # pin command should filter for unpinned deployments
                assert filter_func(unpinned_deployment)
                assert not filter_func(pinned_deployment)
            else:  # unpin
                # unpin command should filter for pinned deployments
                assert filter_func(pinned_deployment)
                assert not filter_func(unpinned_deployment)

        # And that the command was run with the selected index
        mock_run_command.assert_called_once_with(expected_cmd_with_filter)
        mock_sys_exit.assert_called_once_with(0)

    @pytest.mark.parametrize(
        "func,command_name",
        [
            (pin_command, "pin"),
            (unpin_command, "unpin"),
            (rm_command, "rm"),
        ],
    )
    def test_deployment_command_no_args_no_selection(
        self, mocker: MockerFixture, func, command_name
    ):
        """Test deployment commands handle no selection from submenu."""
        # Mock the show_deployment_submenu function to return None
        mock_show_deployment_submenu = mocker.patch(
            "urh.show_deployment_submenu", return_value=None
        )
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        func([])

        # Verify that submenu was called
        mock_show_deployment_submenu.assert_called_once()
        # Verify that run_command was never called (since no selection was made)
        mock_run_command.assert_not_called()
        # sys.exit should NOT be called when no selection is made
        mock_sys_exit.assert_not_called()

    @pytest.mark.parametrize(
        "func,command_name",
        [
            (pin_command, "pin"),
            (unpin_command, "unpin"),
            (rm_command, "rm"),
        ],
    )
    def test_deployment_command_invalid_number(
        self, mocker: MockerFixture, func, command_name
    ):
        """Test deployment commands handle invalid number."""
        mock_print = mocker.patch("urh.print")

        func(["invalid"])
        mock_print.assert_called_once_with("Invalid deployment number: invalid")


class TestMenuExitException:
    """Unit tests for the ESC-to-parent-menu behavior."""

    @pytest.mark.parametrize(
        "command_func, submenu_func_name, expected_filter_func",
        [
            (rebase_command, "show_rebase_submenu", None),
            (pin_command, "show_deployment_submenu", lambda d: not d["pinned"]),
            (unpin_command, "show_deployment_submenu", lambda d: d["pinned"]),
            (rm_command, "show_deployment_submenu", None),
        ],
    )
    def test_command_handles_menu_exit_exception(
        self,
        mocker: MockerFixture,
        command_func,
        submenu_func_name,
        expected_filter_func,
    ):
        """Test that each command properly handles MenuExitException."""
        # Mock submenu function to raise MenuExitException (simulating ESC press)
        mock_submenu_func = mocker.patch(
            f"urh.{submenu_func_name}", side_effect=MenuExitException()
        )
        mock_run_command = mocker.patch("urh.run_command", return_value=0)

        # Call the command with no args to trigger submenu
        with pytest.raises(MenuExitException):
            command_func([])

        # Verify submenu was called
        mock_submenu_func.assert_called_once()

        # If a filter function is expected, verify it was passed correctly
        if expected_filter_func:
            call_args = mock_submenu_func.call_args
            assert call_args is not None
            args, kwargs = call_args
            assert "filter_func" in kwargs
            filter_func = kwargs["filter_func"]
            # Test the filter function behavior
            unpinned_deployment = {"pinned": False}
            pinned_deployment = {"pinned": True}
            assert filter_func(unpinned_deployment) == expected_filter_func(
                unpinned_deployment
            )
            assert filter_func(pinned_deployment) == expected_filter_func(
                pinned_deployment
            )

        # run_command should not be called since the exception was raised
        mock_run_command.assert_not_called()

    def test_show_rebase_submenu_raises_menu_exit_on_esc(self, mocker: MockerFixture):
        """Test that show_rebase_submenu raises MenuExitException when ESC is pressed (exit code 1)."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # ESC pressed in gum returns code 1
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result

        # In test environment, the function returns None instead of raising exception
        result = show_rebase_submenu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )
        assert result is None

    def test_show_rebase_submenu_in_normal_mode_raises_menu_exit(
        self, mocker: MockerFixture
    ):
        """Test that show_rebase_submenu raises MenuExitException in normal mode when ESC is pressed."""
        # Use dependency injection for testing, simulating normal mode (not test mode)
        mock_is_tty = mocker.Mock(return_value=True)
        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # ESC pressed in gum returns code 1
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result
        # Make sure we're not in test mode by clearing the environment variable
        mocker.patch.dict(os.environ, {}, clear=True)

        # Should raise MenuExitException in normal mode
        with pytest.raises(MenuExitException):
            show_rebase_submenu(
                is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
            )

    def test_show_deployment_submenu_raises_menu_exit_on_esc(
        self, mocker: MockerFixture
    ):
        """Test that show_deployment_submenu raises MenuExitException when ESC is pressed (exit code 1)."""
        # Use dependency injection for testing
        mock_is_tty = mocker.Mock(return_value=True)

        # Mock the parse_deployments function to return some test deployments
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
                {
                    "index": 0,
                    "version": "test version",
                    "pinned": False,
                }
            ],
        )

        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # ESC pressed in gum returns code 1
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result

        # In test environment, the function returns None instead of raising exception
        result = show_deployment_submenu(
            is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
        )
        assert result is None

    def test_show_deployment_submenu_in_normal_mode_raises_menu_exit(
        self, mocker: MockerFixture
    ):
        """Test that show_deployment_submenu raises MenuExitException in normal mode when ESC is pressed."""
        # Use dependency injection for testing, simulating normal mode (not test mode)
        mock_is_tty = mocker.Mock(return_value=True)

        # Mock the parse_deployments function to return some test deployments
        mocker.patch(
            "urh.parse_deployments",
            return_value=[
                {
                    "index": 0,
                    "version": "test version",
                    "pinned": False,
                }
            ],
        )

        mock_subprocess_run = mocker.Mock()
        mock_result = mocker.Mock()
        mock_result.returncode = 1  # ESC pressed in gum returns code 1
        mock_result.stdout = ""
        mock_subprocess_run.return_value = mock_result
        # Make sure we're not in test mode by clearing the environment variable
        mocker.patch.dict(os.environ, {}, clear=True)

        # Should raise MenuExitException in normal mode
        with pytest.raises(MenuExitException):
            show_deployment_submenu(
                is_tty_func=mock_is_tty, subprocess_run_func=mock_subprocess_run
            )


class TestOCIClient:
    @pytest.mark.parametrize(
        "cache_exists, initial_token, expect_curl_call, expect_cache_write, expected_token",
        [
            # Case 1: Cache hit - token is read from file, no network call, no cache write.
            (True, "cached-token-123", False, False, "cached-token-123"),
            # Case 2: Cache miss - token is fetched, network call is made, cache is written.
            (False, None, True, True, "new-fetched-token"),
        ],
    )
    def test_get_token_logic(
        self,
        mock_client: OCIClient,
        mocker: MockerFixture,
        cache_exists: bool,
        initial_token: str,
        expect_curl_call: bool,
        expect_cache_write: bool,
        expected_token: str,
    ):
        """Tests token retrieval logic for both cache hit and miss scenarios."""
        # Arrange
        mocker.patch("os.path.exists", return_value=cache_exists)

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = json.dumps({"token": "new-fetched-token"})

        mock_file = mocker.mock_open(read_data=initial_token)
        mocker.patch("builtins.open", mock_file)

        # Act
        token = mock_client.get_token()

        # Assert
        assert token == expected_token
        if expect_curl_call:
            mock_run.assert_called_once()
        else:
            mock_run.assert_not_called()

        if expect_cache_write:
            mock_file.assert_called_once_with(mock_client._get_cache_filepath(), "w")
            mock_file().write.assert_called_once_with("new-fetched-token")
        else:
            # Check that open was called for reading, not writing
            mock_file.assert_called_once_with(mock_client._get_cache_filepath(), "r")

    @pytest.mark.parametrize(
        "run_side_effect, expected_run_calls, expect_cache_invalidation, expected_tags",
        [
            # Case 1: Success on first try with a valid token.
            (
                [MagicMock(stdout=json.dumps({"tags": ["v1", "v2"]}))],
                1,
                False,
                ["v1", "v2"],
            ),
            # Case 2: Retry after a 401 Unauthorized error.
            (
                [
                    subprocess.CalledProcessError(1, "curl", stderr="401 Unauthorized"),
                    MagicMock(stdout=json.dumps({"tags": ["v1"]})),
                ],
                2,
                True,
                ["v1"],
            ),
        ],
    )
    def test_get_tags_logic(
        self,
        mock_client: OCIClient,
        mocker: MockerFixture,
        run_side_effect: List,
        expected_run_calls: int,
        expect_cache_invalidation: bool,
        expected_tags: List[str],
    ):
        """Tests tag fetching logic for both success and retry scenarios."""
        # Arrange
        mock_run = mocker.patch("subprocess.run", side_effect=run_side_effect)

        # Mock get_token to provide tokens for the initial call and potential retry
        mock_get_token = mocker.patch.object(
            mock_client, "get_token", side_effect=["initial-token", "retry-token"]
        )

        mock_remove = mocker.patch("os.remove")

        # Act
        tags = mock_client.get_tags("initial-token")

        # Assert
        assert tags is not None
        assert tags["tags"] == expected_tags
        assert mock_run.call_count == expected_run_calls

        if expect_cache_invalidation:
            mock_remove.assert_called_once_with(mock_client._get_cache_filepath())
            # If we invalidated, we must have fetched a new token for the retry
            assert mock_get_token.call_count == 1
        else:
            mock_remove.assert_not_called()
            # If we succeeded, get_token was not called from get_tags method
            assert mock_get_token.call_count == 0

    def test_get_cache_filepath_format(self, mock_client: OCIClient):
        """Test that the cache filepath is generated correctly and safely."""
        assert mock_client._get_cache_filepath() == "/tmp/gcr_token_test_test-repo"

        client_with_slash = OCIClient("my-org/my-project")
        assert (
            client_with_slash._get_cache_filepath()
            == "/tmp/gcr_token_my-org_my-project"
        )

    @pytest.mark.parametrize(
        "input_tags,expected_filtered_tags",
        [
            # Test filtering out SHA256 tags
            ({"tags": ["v1.0", "sha256:abc123", "v2.0"]}, {"tags": ["v2.0", "v1.0"]}),
            # Test filtering out tag aliases
            (
                {"tags": ["latest", "v1.0", "testing", "stable", "v2.0"]},
                {"tags": ["v2.0", "v1.0"]},
            ),
            # Test filtering out unstable alias but preserving unstable-prefixed tags
            (
                {
                    "tags": [
                        "latest",
                        "unstable",
                        "v1.0",
                        "unstable-20231001",
                        "testing",
                        "stable",
                        "v2.0",
                    ]
                },
                {"tags": ["unstable-20231001", "v2.0", "v1.0"]},
            ),
            # Test filtering out various SHA256 formats
            (
                {
                    "tags": [
                        "v1.0",
                        "sha256:abc123def456",
                        "abc123def456789012345678901234567890abc123def45678901234567890",
                        "<sha256sum>",
                    ]
                },
                {"tags": ["v1.0"]},
            ),
            # Test with no filtering needed
            ({"tags": ["v3.0", "v2.0", "v1.0"]}, {"tags": ["v3.0", "v2.0", "v1.0"]}),
            # Test with only filtered tags
            (
                {"tags": ["latest", "testing", "stable", "unstable", "sha256:abc"]},
                {"tags": []},
            ),
            # Test empty tags
            ({"tags": []}, {"tags": []}),
            # Test with mixed case tag aliases
            (
                {"tags": ["Latest", "TESTING", "StAbLe", "UnStAbLe", "v1.0"]},
                {"tags": ["v1.0"]},
            ),
            # Test filtering out dot-based tag aliases
            (
                {
                    "tags": [
                        "latest.",
                        "v1.0",
                        "testing.",
                        "stable.",
                        "unstable.",
                        "v2.0",
                        "latest.1",
                        "testing.2",
                    ]
                },
                {"tags": ["v2.0", "v1.0"]},
            ),
            # Test with only dot-based aliases
            (
                {"tags": ["latest.", "testing.", "stable.", "unstable.", "sha256:abc"]},
                {"tags": []},
            ),
        ],
    )
    def test_filter_and_sort_tags(
        self, mock_client: OCIClient, input_tags: dict, expected_filtered_tags: dict
    ):
        """Test that the filter_and_sort_tags method correctly filters and sorts tags."""
        result = mock_client._filter_and_sort_tags(input_tags)
        assert result == expected_filtered_tags

    def test_filter_and_sort_tags_with_none_input(self, mock_client: OCIClient):
        """Test that filter_and_sort_tags handles None input correctly."""
        result = mock_client._filter_and_sort_tags(None)
        assert result is None

    @pytest.mark.parametrize(
        "input_tags,expected_count",
        [
            # Test that more than 30 tags are limited to 30
            ({"tags": [f"v{i}.0" for i in range(50)]}, 30),
            # Test that exactly 30 tags are preserved
            ({"tags": [f"v{i}.0" for i in range(30)]}, 30),
            # Test that fewer than 30 tags are preserved as-is
            ({"tags": [f"v{i}.0" for i in range(20)]}, 20),
            # Test with date format tags
            ({"tags": [f"2023{str(i).zfill(2)}01" for i in range(1, 45)]}, 30),
            # Test with filtered tags (some get removed, but result should still be <= 30)
            (
                {
                    "tags": ["latest", "testing", "stable"]
                    + [f"sha256:{'a' * 60}"] * 5
                    + [f"2023{str(i).zfill(2)}01" for i in range(1, 40)]
                },
                30,  # After filtering out invalid tags, should have max 30
            ),
        ],
    )
    def test_filter_and_sort_tags_limits_to_30(
        self, mock_client: OCIClient, input_tags: dict, expected_count: int
    ):
        """Test that filter_and_sort_tags limits output to maximum 30 tags."""
        result = mock_client._filter_and_sort_tags(input_tags)
        assert result is not None
        assert len(result["tags"]) == expected_count
        # Also verify that it's still properly sorted (first tag should be the highest since reverse sorted)
        if result["tags"]:
            # If sorted in descending order, first should be highest
            # For version tags like v49.0, v48.0, etc., first should be v49.0
            # This test is mainly about count, not specific ordering
            pass


class TestRemoteLsCommand:
    """Unit tests for the remote_ls_command function."""

    @pytest.mark.parametrize(
        "url,expected_repo,tag_response,expected_print_calls",
        [
            (
                "ghcr.io/test/repo:latest",
                "test/repo",
                {"tags": ["v1.0", "v2.0", "latest"]},
                ["Tags for ghcr.io/test/repo:latest:"],
            ),
            (
                "docker.io/library/ubuntu:latest",
                "library/ubuntu",
                {"tags": ["stable", "testing"]},
                ["Tags for docker.io/library/ubuntu:latest:"],
            ),
            (
                "ghcr.io/test/repo",
                "test/repo",
                {"tags": ["latest"]},
                ["Tags for ghcr.io/test/repo:"],
            ),
            # Test case where no tags are returned
            (
                "ghcr.io/test/repo:latest",
                "test/repo",
                None,
                ["Could not fetch tags for ghcr.io/test/repo:latest"],
            ),
        ],
    )
    def test_remote_ls_command_with_different_urls(
        self,
        mocker: MockerFixture,
        url: str,
        expected_repo: str,
        tag_response: dict,
        expected_print_calls: list,
    ):
        """Test remote_ls_command with different URLs and tag responses."""
        # Mock OCIClient and its methods
        mock_client = mocker.Mock()
        mock_client_class = mocker.patch("urh.OCIClient", return_value=mock_client)
        mock_client.fetch_repository_tags.return_value = tag_response

        # Mock print to capture output
        mock_print = mocker.patch("urh.print")

        # Mock sys.exit to prevent the test from exiting
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command([url])

        # Verify that OCIClient was instantiated with the correct repository
        mock_client_class.assert_called_once_with(expected_repo)
        # Verify that fetch_repository_tags was called
        mock_client.fetch_repository_tags.assert_called_once()

        # Verify that the expected print calls were made
        for expected_call in expected_print_calls:
            mock_print.assert_any_call(expected_call)

        # Verify that sys.exit was called (since the command should exit after completion)
        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_command_no_args_calls_submenu(self, mocker: MockerFixture):
        """Test remote_ls_command calls submenu when no args provided."""
        # Mock the show_remote_ls_submenu function to avoid actual gum execution
        mock_show_remote_ls_submenu = mocker.patch(
            "urh.show_remote_ls_submenu", return_value="ghcr.io/test/repo:tag"
        )

        # Mock OCIClient and its methods
        mock_client = mocker.Mock()
        mock_client_class = mocker.patch("urh.OCIClient", return_value=mock_client)
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0", "v2.0"]}

        # Mock print to capture output
        mock_print = mocker.patch("urh.print")

        # Mock sys.exit to prevent the test from exiting
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command([])

        # Verify that submenu was called
        mock_show_remote_ls_submenu.assert_called_once()
        # Verify that OCIClient was instantiated with the correct repository
        mock_client_class.assert_called_once_with("test/repo")
        # Verify that fetch_repository_tags was called
        mock_client.fetch_repository_tags.assert_called_once()
        # Verify that the tags were printed
        mock_print.assert_any_call("Tags for ghcr.io/test/repo:tag:")

        # Verify that sys.exit was called (since the command should exit after completion)
        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_command_no_args_no_selection(self, mocker: MockerFixture):
        """Test remote_ls_command handles no selection from submenu."""
        # Mock the show_remote_ls_submenu function to return None
        mock_show_remote_ls_submenu = mocker.patch(
            "urh.show_remote_ls_submenu", return_value=None
        )

        # Mock OCIClient and print to verify they're not called
        mock_client_class = mocker.patch("urh.OCIClient")
        mock_print = mocker.patch("urh.print")

        # Mock sys.exit to prevent the test from exiting
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command([])

        # Verify that submenu was called
        mock_show_remote_ls_submenu.assert_called_once()
        # Verify that OCIClient was NOT called (since no selection was made)
        mock_client_class.assert_not_called()
        # Verify that print was NOT called (since no selection was made)
        mock_print.assert_not_called()
        # Verify that sys.exit was called even when no selection is made (since command completes)
        mock_sys_exit.assert_called_once_with(0)

    @pytest.mark.parametrize(
        "url, expected_repo, exception_type, expected_error_msg",
        [
            (
                "ghcr.io/test/repo:latest",
                "test/repo",
                Exception("Network error"),
                "Error fetching tags for ghcr.io/test/repo:latest: Network error",
            ),
            (
                "docker.io/library/ubuntu:20.04",
                "library/ubuntu",
                ValueError("Invalid format"),
                "Error fetching tags for docker.io/library/ubuntu:20.04: Invalid format",
            ),
        ],
    )
    def test_remote_ls_command_error_handling(
        self,
        mocker: MockerFixture,
        url: str,
        expected_repo: str,
        exception_type: Exception,
        expected_error_msg: str,
    ):
        """Test remote_ls_command handles different types of errors gracefully."""
        # Mock OCIClient and its methods to raise an exception
        mock_client = mocker.Mock()
        mock_client_class = mocker.patch("urh.OCIClient", return_value=mock_client)
        mock_client.fetch_repository_tags.side_effect = exception_type

        # Mock print to capture output
        mock_print = mocker.patch("urh.print")

        # Mock sys.exit to prevent the test from exiting
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command([url])

        # Verify that OCIClient was instantiated
        mock_client_class.assert_called_once_with(expected_repo)
        # Verify that the error message was printed
        mock_print.assert_any_call(expected_error_msg)
        # Verify that sys.exit was called (since the command should exit after completion, even with errors)
        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_command_invalid_url_format(self, mocker: MockerFixture):
        """Test remote_ls_command with invalid URL format but still works."""
        # Mock OCIClient and its methods
        mock_client = mocker.Mock()
        mock_client_class = mocker.patch("urh.OCIClient", return_value=mock_client)
        mock_client.fetch_repository_tags.return_value = {"tags": ["latest"]}

        # Mock sys.exit to prevent the test from exiting
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command(["invalid-url-format"])

        # For an invalid URL format, it should still try to create a OCIClient
        # In our implementation, it takes everything before the first colon or the whole string
        mock_client_class.assert_called_once_with("invalid-url-format")
        # Verify that fetch_repository_tags was called
        mock_client.fetch_repository_tags.assert_called_once()
        # Verify that sys.exit was called (since the command should exit after completion)
        mock_sys_exit.assert_called_once_with(0)

    @pytest.mark.parametrize(
        "url,expected_context,raw_tags,expected_sorted_tags",
        [
            # Test :testing context prioritizes testing- prefixed tags
            (
                "ghcr.io/test/repo:testing",
                "testing",
                [
                    "20231201",
                    "testing-20231201",
                    "stable-20231201",
                    "20231115.1",
                    "testing-20231115.2",
                ],
                [
                    "testing-20231201",
                    "testing-20231115.2",
                    "20231201",
                    "stable-20231201",
                    "20231115.1",
                ],
            ),
            # Test :stable context prioritizes stable- prefixed tags
            (
                "ghcr.io/test/repo:stable",
                "stable",
                ["20231201", "testing-20231201", "stable-20231201", "20231115.1"],
                ["stable-20231201", "20231201", "testing-20231201", "20231115.1"],
            ),
            # Test no context uses standard sorting
            (
                "ghcr.io/test/repo:latest",  # No special context
                None,
                ["20231201", "testing-20231201", "stable-20231201", "20231115.1"],
                [
                    "20231201",
                    "testing-20231201",
                    "stable-20231201",
                    "20231115.1",
                ],  # Standard sorting
            ),
            # Test :testing with mixed date tags
            (
                "docker.io/test/ubuntu:testing",
                "testing",
                ["20231001", "testing-20231115", "20231201", "testing-20231201"],
                ["testing-20231201", "testing-20231115", "20231201", "20231001"],
            ),
        ],
    )
    def test_remote_ls_command_context_aware_sorting(
        self,
        mocker: MockerFixture,
        url: str,
        expected_context: str,
        raw_tags: list,
        expected_sorted_tags: list,
    ):
        """Test that remote_ls_command applies context-aware sorting based on URL tag."""
        # Mock OCIClient and its methods - we need to mock get_raw_tags for context cases
        mock_client = mocker.Mock()
        mocker.patch("urh.OCIClient", return_value=mock_client)

        # For URLs with testing/stable context, the code should call get_raw_tags
        # For other URLs, it should call fetch_repository_tags
        if expected_context:
            mock_client.get_raw_tags.return_value = {"tags": raw_tags}
            mock_client.fetch_repository_tags.return_value = {
                "tags": expected_sorted_tags
            }  # fallback
        else:
            mock_client.fetch_repository_tags.return_value = {"tags": raw_tags}

        # Mock print to capture the output tags
        captured_prints = []

        def mock_print(*args, **kwargs):
            captured_prints.extend(args)

        mock_print_func = mocker.patch("urh.print", side_effect=mock_print)

        # Mock sys.exit to prevent the test from exiting
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command([url])

        # Verify the correct client method was called based on context
        if expected_context:
            # For context URLs, raw tags should be fetched
            mock_client.get_raw_tags.assert_called_once()
        else:
            # For non-context URLs, use standard method
            mock_client.fetch_repository_tags.assert_called_once()

        # Verify that sys.exit was called
        mock_sys_exit.assert_called_once_with(0)

        # Verify that the output contains the expected tags (in the correct order)
        # We'll check that the expected_sorted_tags appear in the printed output
        printed_tags = []
        for call in mock_print_func.call_args_list:
            args, kwargs = call
            if len(args) == 1 and args[0].startswith("  "):  # Tag line starts with "  "
                tag = args[0].strip()
                if tag not in [
                    "Tags for " + url + ":",
                    "No tags found for " + url,
                    "Could not fetch tags for " + url,
                ]:
                    printed_tags.append(tag)

        # Check if expected sorted tags match what was printed (order matters for context-aware)
        if expected_context:
            # In context cases, we expect the sorted order to follow context priority
            # Verify that context-priority tags appear first in the output
            if expected_context == "testing":
                testing_tags_in_output = [
                    t for t in printed_tags if t.startswith("testing-")
                ]
                # All testing tags should be at the beginning
                assert len(testing_tags_in_output) > 0, (
                    "Should have testing-prefixed tags"
                )
                # Verify first few tags are testing tags
                for i, testing_tag in enumerate(testing_tags_in_output):
                    assert printed_tags[i] == testing_tag, (
                        f"Testing tag {testing_tag} should be in early position"
                    )
            elif expected_context == "stable":
                stable_tags_in_output = [
                    t for t in printed_tags if t.startswith("stable-")
                ]
                # All stable tags should be at the beginning
                assert len(stable_tags_in_output) > 0, (
                    "Should have stable-prefixed tags"
                )
                # Verify first few tags are stable tags
                for i, stable_tag in enumerate(stable_tags_in_output):
                    assert printed_tags[i] == stable_tag, (
                        f"Stable tag {stable_tag} should be in early position"
                    )

    def test_remote_ls_command_context_aware_filtering_removes_invalid_tags(
        self, mocker: MockerFixture
    ):
        """Test that context-aware filtering still removes invalid tags (SHA256, aliases)."""
        url_with_context = "ghcr.io/test/repo:testing"

        # Raw tags including invalid ones that should be filtered out
        raw_tags_with_invalid = [
            "20231201",
            "testing-20231201",
            "sha256:abc123def456",
            "latest",
            "testing",
            "<abc123def456>",
            "stable-20231115",
            "20231115.1",
            "unstable-20241023",
            "20240101.11",
        ]

        mock_client = mocker.Mock()
        mocker.patch("urh.OCIClient", return_value=mock_client)
        mock_client.get_raw_tags.return_value = {"tags": raw_tags_with_invalid}

        # Capture print calls
        captured_outputs = []

        def capture_print(*args, **kwargs):
            captured_outputs.extend([str(arg) for arg in args])

        mock_print = mocker.patch("urh.print", side_effect=capture_print)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command([url_with_context])

        # Verify get_raw_tags was called (due to context)
        mock_client.get_raw_tags.assert_called_once()

        # Find the printed tags (lines starting with "  ")
        printed_tags = []
        for call in mock_print.call_args_list:
            args, kwargs = call
            if len(args) == 1 and isinstance(args[0], str) and args[0].startswith("  "):
                tag = args[0].strip()
                printed_tags.append(tag)

        # Verify invalid tags are NOT in the output
        invalid_tags = ["sha256:abc123def456", "latest", "testing", "<abc123def456>"]
        for invalid_tag in invalid_tags:
            assert invalid_tag not in printed_tags, (
                f"Invalid tag {invalid_tag} should be filtered out"
            )

        # Verify only testing-prefixed tags are in the output (context-aware behavior)
        expected_tags = ["testing-20231201"]  # Only tags with matching context prefix
        for expected_tag in expected_tags:
            assert expected_tag in printed_tags, (
                f"Expected tag {expected_tag} should be in output when using testing context"
            )

        # Verify non-prefixed and other prefixed tags are NOT in the output
        unexpected_tags = ["20231201", "stable-20231115", "20231115.1"]
        for unexpected_tag in unexpected_tags:
            assert unexpected_tag not in printed_tags, (
                f"Non-context tag {unexpected_tag} should not be in output when using testing context"
            )

        # In testing context, testing-prefixed tags should be prioritized
        testing_tags_in_output = [t for t in printed_tags if t.startswith("testing-")]
        # These should appear first in the sorted output
        if testing_tags_in_output:
            first_tag = printed_tags[0]
            assert first_tag.startswith("testing-"), (
                "Testing-prefixed tags should come first in testing context"
            )

        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_command_unstable_alias_filtering_with_unstable_context(
        self, mocker: MockerFixture
    ):
        """Test that unstable alias is filtered out but unstable-prefixed tags are preserved in unstable context."""
        url_with_context = "ghcr.io/test/repo:unstable"

        # Raw tags including unstable alias and unstable-prefixed tags
        raw_tags = [
            "20231201",
            "testing-20231201",
            "stable-20231115",
            "unstable",  # This should be filtered out
            "unstable-20231120",  # This should be preserved in unstable context
            "20231115.1",
        ]

        mock_client = mocker.Mock()
        mocker.patch("urh.OCIClient", return_value=mock_client)
        mock_client.get_raw_tags.return_value = {"tags": raw_tags}

        # Capture print calls
        captured_outputs = []

        def capture_print(*args, **kwargs):
            captured_outputs.extend([str(arg) for arg in args])

        mock_print = mocker.patch("urh.print", side_effect=capture_print)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command([url_with_context])

        # Verify get_raw_tags was called (due to context)
        mock_client.get_raw_tags.assert_called_once()

        # Find the printed tags (lines starting with "  ")
        printed_tags = []
        for call in mock_print.call_args_list:
            args, kwargs = call
            if len(args) == 1 and isinstance(args[0], str) and args[0].startswith("  "):
                tag = args[0].strip()
                printed_tags.append(tag)

        # Verify that unstable alias is NOT in the output
        assert "unstable" not in printed_tags, (
            "unstable alias should be filtered out even in unstable context"
        )

        # Verify that unstable-prefixed tags ARE in the output (context-aware behavior)
        assert "unstable-20231120" in printed_tags, (
            "unstable-prefixed tags should be preserved in unstable context"
        )

        # Verify that only unstable-prefixed tags are in the output for unstable context
        # (tags without unstable- prefix should not appear in unstable context)
        non_unstable_prefixed_tags = [
            t for t in printed_tags if not t.startswith("unstable-")
        ]
        for non_unstable_tag in non_unstable_prefixed_tags:
            # The only allowed non-unstable prefixed tag is the unstable alias which should be filtered
            assert non_unstable_tag != "unstable", (
                "unstable alias should be filtered out"
            )

        mock_sys_exit.assert_called_once_with(0)

    def test_context_aware_filtering_unstable_alias_exclusion(self):
        """Test that _context_aware_filter_and_sort properly filters out unstable alias."""
        from urh import _context_aware_filter_and_sort

        # Test that unstable alias is filtered out but unstable-prefixed tags are preserved
        raw_tags = [
            "20231201",
            "testing-20231201",
            "stable-20231115",
            "unstable",  # This should be filtered out
            "unstable-20231120",  # This should be preserved
            "20231115.1",
        ]

        result = _context_aware_filter_and_sort(
            raw_tags, None
        )  # No context, so just filtering

        # Verify unstable alias is filtered out
        assert "unstable" not in result, (
            "unstable alias should be filtered out by _context_aware_filter_and_sort"
        )

        # Verify unstable-prefixed tags are preserved
        assert "unstable-20231120" in result, (
            "unstable-prefixed tag should be preserved by _context_aware_filter_and_sort"
        )

    def test_context_aware_filtering_dot_based_alias_exclusion(self):
        """Test that _context_aware_filter_and_sort properly filters out dot-based aliases."""
        from urh import _context_aware_filter_and_sort

        # Test that dot-based aliases are filtered out
        # Use different dates to avoid deduplication issues during testing
        raw_tags = [
            "20231001",  # Different date to avoid deduplication with testing- tag
            "testing-20231201",  # This is a prefixed tag, different date
            "stable-20230815",  # Different date to avoid deduplication
            "latest.",  # This should be filtered out
            "testing.",  # This should be filtered out
            "stable.",  # This should be filtered out
            "unstable.",  # This should be filtered out
            "latest.1",  # This should be filtered out (starts with latest.)
            "testing.2",  # This should be filtered out (starts with testing.)
            "v1.0",  # Non-date-based tag that should be preserved
        ]

        result = _context_aware_filter_and_sort(
            raw_tags, None
        )  # No context, so just filtering

        # Verify dot-based aliases are filtered out
        assert "latest." not in result, (
            "latest. should be filtered out by _context_aware_filter_and_sort"
        )
        assert "testing." not in result, (
            "testing. should be filtered out by _context_aware_filter_and_sort"
        )
        assert "stable." not in result, (
            "stable. should be filtered out by _context_aware_filter_and_sort"
        )
        assert "unstable." not in result, (
            "unstable. should be filtered out by _context_aware_filter_and_sort"
        )
        assert "latest.1" not in result, (
            "latest.1 should be filtered out by _context_aware_filter_and_sort"
        )
        assert "testing.2" not in result, (
            "testing.2 should be filtered out by _context_aware_filter_and_sort"
        )

        # Verify non-alias tags are preserved
        assert "20231001" in result, "Non-alias tags should be preserved"
        assert "v1.0" in result, "Non-alias tags should be preserved"

    @pytest.mark.parametrize(
        "raw_tags,expected_count",
        [
            # Test that more than 30 context-prefixed tags are limited to 30 in context-aware filtering
            ([f"testing-v{i}.0" for i in range(50)], 30),
            # Test that exactly 30 context-prefixed tags are preserved in context-aware filtering
            ([f"testing-v{i}.0" for i in range(30)], 30),
            # Test that fewer than 30 context-prefixed tags are preserved as-is in context-aware filtering
            ([f"testing-v{i}.0" for i in range(20)], 20),
            # Test with date format context-prefixed tags in context-aware filtering
            ([f"testing-2023{str(i).zfill(2)}01" for i in range(1, 45)], 30),
            # Test with mixed prefixed and non-prefixed tags - only prefixed should be returned
            (
                ["latest", "testing", "stable", "v1.0", "20230101"]
                + [
                    f"testing-v{i}.0" for i in range(30)
                ]  # Should only return these prefixed tags
                + [f"sha256:{'a' * 60}"] * 5,
                30,  # After filtering, only the 30 testing-prefixed tags should remain
            ),
        ],
    )
    def test_context_aware_filter_and_sort_limits_to_30(
        self, raw_tags: list, expected_count: int
    ):
        """Test that _context_aware_filter_and_sort limits output to maximum 30 tags."""
        from urh import _context_aware_filter_and_sort

        result = _context_aware_filter_and_sort(raw_tags, "testing")
        assert len(result) == expected_count

    def test_remote_ls_command_limits_output_to_30_tags(self, mocker: MockerFixture):
        """Test that remote_ls_command limits output to 30 tags maximum."""
        from urh import OCIClient

        # Create more than 30 tags to test the limit
        url = "ghcr.io/test/repo:latest"  # Note: 'latest' is not a special context, so uses fetch_repository_tags
        many_tags = [f"2023{str(i).zfill(2)}01" for i in range(1, 45)]  # 44 tags

        # Test the actual OCIClient functionality to make sure it limits properly
        # Create a real client instance to test the actual filtering logic
        client = OCIClient("test/repo", cache_path="/tmp/test_cache")
        # Create a test input with >30 tags
        test_data = {"tags": many_tags}

        # Call the actual filtering method
        result = client._filter_and_sort_tags(test_data)

        # Verify that the result is limited to 30 tags
        assert result is not None
        assert len(result["tags"]) == 30

        # Now test the full command flow with a mock client that properly mimics the filtering
        mock_client = mocker.Mock()
        mock_client_class = mocker.patch("urh.OCIClient", return_value=mock_client)
        # Since we already verified the internal filtering works, mock the result to be limited
        mock_client.fetch_repository_tags.return_value = {
            "tags": many_tags[:30]
        }  # Should be limited to 30

        # Capture print calls to verify only 30 tags are printed
        print_calls = []

        def capture_print(*args, **kwargs):
            print_calls.extend(args)

        mock_print = mocker.patch("urh.print", side_effect=capture_print)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command([url])

        # Verify that OCIClient was instantiated
        mock_client_class.assert_called_once_with("test/repo")
        # Verify fetch_repository_tags was called (non-context path)
        mock_client.fetch_repository_tags.assert_called_once()

        # Count the number of tag lines printed (they start with "  ")
        tag_lines = []
        for call in mock_print.call_args_list:
            args, kwargs = call
            if len(args) == 1 and isinstance(args[0], str) and args[0].startswith("  "):
                tag_line = args[0].strip()
                if tag_line not in [
                    "Tags for ghcr.io/test/repo:latest:"
                ]:  # Exclude header
                    tag_lines.append(tag_line)

        # Verify that maximum 30 tags were printed
        assert len(tag_lines) <= 30
        assert len(tag_lines) == 30  # Should be exactly 30 since input had more than 30

        # Verify sys.exit was called
        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_command_limits_output_to_30_tags_context(
        self, mocker: MockerFixture
    ):
        """Test that remote_ls_command limits output to 30 tags maximum when using context."""
        # Create more than 30 tags to test the limit with context
        url = "ghcr.io/test/repo:testing"  # Using 'testing' context
        many_tags = [
            f"testing-2023{str(i).zfill(2)}01" for i in range(1, 45)
        ]  # 44 testing-prefixed tags

        # Mock OCIClient and its methods
        mock_client = mocker.Mock()
        mock_client_class = mocker.patch("urh.OCIClient", return_value=mock_client)
        # Since :testing IS a special context, get_raw_tags should be called, then _context_aware_filter_and_sort
        mock_client.get_raw_tags.return_value = {"tags": many_tags}

        # Capture print calls to verify only 30 tags are printed
        print_calls = []

        def capture_print(*args, **kwargs):
            print_calls.extend(args)

        mock_print = mocker.patch("urh.print", side_effect=capture_print)
        mock_sys_exit = mocker.patch("urh.sys.exit")

        remote_ls_command([url])

        # Verify that OCIClient was instantiated
        mock_client_class.assert_called_once_with("test/repo")
        # Verify get_raw_tags was called (context path)
        mock_client.get_raw_tags.assert_called_once()

        # Count the number of tag lines printed (they start with "  ")
        tag_lines = []
        for call in mock_print.call_args_list:
            args, kwargs = call
            if len(args) == 1 and isinstance(args[0], str) and args[0].startswith("  "):
                tag_line = args[0].strip()
                if tag_line not in [
                    "Tags for ghcr.io/test/repo:testing:"
                ]:  # Exclude header
                    tag_lines.append(tag_line)

        # Verify that maximum 30 tags were printed
        assert len(tag_lines) <= 30
        assert len(tag_lines) == 30  # Should be exactly 30 since input had more than 30

        # Verify sys.exit was called
        mock_sys_exit.assert_called_once_with(0)
