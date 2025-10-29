"""Unit tests for ublue-rebase-helper (urh.py)."""

import subprocess
import os
import sys
import pytest
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
    upgrade_command,
    show_rebase_submenu,
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
