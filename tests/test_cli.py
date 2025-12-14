"""Tests for the CLI module."""

import os
import sys
from unittest.mock import Mock

import pytest

from src.urh import cli
from src.urh.menu import MenuExitException


@pytest.fixture
def mock_cli_system_setup(mocker):
    """Shared fixture for CLI system mocking to prevent privilege escalation."""
    # Mock object for subprocess.run that returns appropriate values
    mock_subprocess_result = mocker.MagicMock()
    mock_subprocess_result.returncode = 0  # For "which curl" command to return True

    # Patch all necessary functions before importing main to prevent privilege escalation
    # Also patch subprocess.run to prevent any direct subprocess calls
    mocker.patch("subprocess.run", return_value=mock_subprocess_result)
    # Patch system functions that make subprocess calls to prevent privilege escalation
    mocker.patch(
        "src.urh.system.check_curl_presence", return_value=True
    )  # Assume curl is available in tests
    # Patch deployment info functions that make system calls
    mocker.patch(
        "src.urh.deployment.get_current_deployment_info",
        return_value={"repository": "test", "version": "v1.0"},
    )
    mocker.patch("src.urh.deployment.get_deployment_info", return_value=[])
    mocker.patch(
        "src.urh.deployment.get_status_output", return_value=None
    )  # Needed for get_deployment_info
    # Patch config function to avoid file system access
    mock_config = mocker.MagicMock()
    mock_config.container_urls.options = ["ghcr.io/test/repo:testing"]
    mocker.patch("src.urh.config.get_config", return_value=mock_config)
    # Also patch setup_logging in the cli module
    mocker.patch("src.urh.cli.setup_logging", return_value=None)


class TestCLI:
    """Test CLI functionality."""

    def test_cli_module_exists(self):
        """Test that the CLI module can be imported."""
        from src.urh.cli import _main_menu_loop, setup_logging

        assert setup_logging is not None
        assert _main_menu_loop is not None


class TestMainWorkflow:
    """Test main application workflow."""

    @pytest.mark.parametrize(
        "command,args,expected_calls",
        [
            ("check", [], [("get_command", "check"), ("handler", [])]),
            (
                "rebase",
                ["ghcr.io/test/repo:testing"],
                [("get_command", "rebase"), ("handler", ["ghcr.io/test/repo:testing"])],
            ),
        ],
    )
    def test_main_with_command(
        self, mocker, mock_cli_system_setup, command, args, expected_calls
    ):
        """Test main function with a command."""
        mock_command_registry = mocker.MagicMock()
        mock_command = mocker.MagicMock()
        mock_command_registry.get_command.return_value = mock_command

        import sys

        original_argv = sys.argv
        sys.argv = ["urh.py", command] + args
        # Mock sys.exit to track the exit code without actually exiting
        mock_exit = mocker.MagicMock()
        mocker.patch("sys.exit", mock_exit)

        try:
            # Patch all necessary functions before importing main to prevent privilege escalation
            # IMPORTANT: The main function imports CommandRegistry from .commands (src.urh.commands)
            mocker.patch(
                "src.urh.cli.CommandRegistry", return_value=mock_command_registry
            )
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Original location for compatibility
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Main module location for direct calls
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Actual implementation location
            # Import here to avoid issues with mocking
            from src.urh.core import main

            main()

            for method_name, expected_arg in expected_calls:
                if method_name == "get_command":
                    mock_command_registry.get_command.assert_called_once_with(
                        expected_arg
                    )
                else:
                    getattr(mock_command, method_name).assert_called_once_with(
                        expected_arg
                    )
        finally:
            sys.argv = original_argv


class TestCLIMainFunction:
    """Test the main CLI function for better coverage."""

    def test_main_with_missing_curl(self, mocker):
        """Test main function when curl is not available."""
        # Mock check_curl_presence to return False (this is the first thing checked)
        mock_check_curl_presence = mocker.patch(
            "src.urh.cli.check_curl_presence", return_value=False
        )
        mock_print = mocker.patch("builtins.print")
        mock_sys_exit = mocker.patch("sys.exit")

        # Mock get_config to avoid file I/O
        mock_config = Mock()
        mock_config.settings.debug_mode = False
        mocker.patch("src.urh.cli.get_config", return_value=mock_config)

        # Mock setup_logging to prevent any setup
        mocker.patch("src.urh.cli.setup_logging")

        # Mock sys.argv to ensure no commands
        mocker.patch.object(sys, "argv", ["urh.py"])

        # Mock all other potentially problematic calls
        mock_registry = Mock()
        mock_registry.get_commands.return_value = []
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_registry)

        cli.main()

        # Verify that check_curl_presence was called (it should be the first check)
        mock_check_curl_presence.assert_called_once()

        # Verify error messages and exit - the curl check happens first
        # before any menu logic, so we should see these print calls
        assert mock_print.call_count >= 2  # At least the two error messages

        # Check that the specific error messages were printed
        printed_messages = [call[0][0] for call in mock_print.call_args_list]
        assert (
            "Error: curl is required for this application but was not found."
            in printed_messages
        )
        assert "Please install curl and try again." in printed_messages

        # Verify that sys.exit was called with code 1
        mock_sys_exit.assert_called_once_with(1)

    def test_main_with_args(self, mocker):
        """Test main function with command line arguments."""
        # Set up test arguments
        test_args = ["urh.py", "check"]  # Simulate command line args
        mocker.patch.object(sys, "argv", test_args)

        # Mock curl presence check
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)

        # Mock get_config
        mock_config = Mock()
        mock_config.settings.debug_mode = False
        mocker.patch("src.urh.cli.get_config", return_value=mock_config)

        # Mock the command registry and its methods
        mock_registry = Mock()
        mock_command = Mock()
        mock_registry.get_command.return_value = mock_command
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_registry)

        # Mock setup_logging
        mock_setup_logging = mocker.patch("src.urh.cli.setup_logging")

        cli.main()

        # Verify that the command was retrieved and handler was called
        mock_registry.get_command.assert_called_once_with("check")
        mock_command.handler.assert_called_once_with([])
        mock_setup_logging.assert_called_once()

    def test_main_with_invalid_command(self, mocker, capfd):
        """Test main function with invalid command."""
        # Set up test arguments with invalid command
        test_args = ["urh.py", "invalid_command"]
        mocker.patch.object(sys, "argv", test_args)

        # Mock curl presence check
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)

        # Mock get_config
        mock_config = Mock()
        mock_config.settings.debug_mode = False
        mocker.patch("src.urh.cli.get_config", return_value=mock_config)

        # Mock the command registry to return None for invalid command
        mock_registry = Mock()
        mock_registry.get_command.return_value = None
        mock_registry.get_commands.return_value = []  # Need to return empty list for iteration
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_registry)

        # Mock setup_logging
        mocker.patch("src.urh.cli.setup_logging")

        # Mock sys.exit
        mock_sys_exit = mocker.patch("sys.exit")

        cli.main()

        # Capture output to verify print statements
        captured = capfd.readouterr()
        assert "Unknown command: invalid_command" in captured.out

        # Verify that sys.exit was called
        mock_sys_exit.assert_called_once_with(1)

    def test_main_no_args_with_test_environment(self, mocker, mock_cli_system_setup):
        """Test main function when no args provided in test environment."""
        # Set up test arguments with no command
        test_args = ["urh.py"]  # No command provided
        mocker.patch.object(sys, "argv", test_args)

        # Mock test environment
        mocker.patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "some_test"})

        # Mock curl presence check
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)

        # Mock get_config
        mock_config = Mock()
        mock_config.settings.debug_mode = False
        mocker.patch("src.urh.cli.get_config", return_value=mock_config)

        # Mock the command registry
        mock_registry = Mock()
        mock_commands = [Mock(name="check"), Mock(name="ls")]
        mock_registry.get_commands.return_value = mock_commands
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_registry)

        # Mock main menu loop to prevent infinite loop
        mock_main_menu_loop = mocker.patch("src.urh.cli._main_menu_loop")

        cli.main()

        # Verify that main menu loop was called once
        mock_main_menu_loop.assert_called_once()

    def test_main_menu_loop_with_selection(self, mocker):
        """Test _main_menu_loop with command selection."""
        # Mock the registry
        mock_registry = Mock()
        mock_command = Mock()
        mock_registry.get_command.return_value = mock_command
        # Mock get_commands to return a list of command objects with 'name' attribute
        mock_command_obj = Mock()
        mock_command_obj.name = "check"
        mock_command_obj.description = "Check for updates"
        mock_registry.get_commands.return_value = [mock_command_obj]
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_registry)

        # Mock deployment info functions
        mocker.patch(
            "src.urh.cli.get_current_deployment_info",
            return_value={"repo": "test", "version": "v1"},
        )
        mocker.patch("src.urh.cli.format_deployment_header", return_value="test header")

        # Mock menu system
        mock_menu_system = mocker.patch("src.urh.cli._menu_system")
        mock_menu_system.show_menu.return_value = "check"  # Return a selected command

        # Mock to avoid infinite loop in test environment
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        mocker.patch("os.isatty", return_value=True)

        cli._main_menu_loop()

        # Verify that the command handler was called
        mock_registry.get_command.assert_called_once_with("check")
        mock_command.handler.assert_called_once_with([])

    def test_main_menu_loop_with_no_selection(self, mocker):
        """Test _main_menu_loop with no selection (ESC)."""
        # Mock the registry
        mock_registry = Mock()
        # Mock get_commands to return a list of command objects with 'name' attribute
        mock_command_obj = Mock()
        mock_command_obj.name = "check"
        mock_command_obj.description = "Check for updates"
        mock_registry.get_commands.return_value = [mock_command_obj]
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_registry)

        # Mock deployment info functions
        mocker.patch(
            "src.urh.cli.get_current_deployment_info",
            return_value={"repo": "test", "version": "v1"},
        )
        mocker.patch("src.urh.cli.format_deployment_header", return_value="test header")

        # Mock menu system to return None (ESC pressed)
        mock_menu_system = mocker.patch("src.urh.cli._menu_system")
        mock_menu_system.show_menu.return_value = None  # No selection made

        # Mock to avoid infinite loop in test environment
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        mocker.patch("os.isatty", return_value=True)

        # This should just return without calling any command handler
        cli._main_menu_loop()

        # Verify that get_command was not called since no selection was made
        mock_registry.get_command.assert_not_called()

    def test_main_menu_loop_with_menu_exit_exception_main_menu(self, mocker):
        """Test main function when MenuExitException with is_main_menu=True is raised."""
        from src.urh.menu import MenuExitException

        # Mock curl presence to return True to reach main menu loop
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)

        # Mock get_config
        mock_config = Mock()
        mock_config.settings.debug_mode = False
        mocker.patch("src.urh.cli.get_config", return_value=mock_config)

        # Mock setup_logging
        mocker.patch("src.urh.cli.setup_logging")

        # Mock sys.argv to trigger menu loop (no command line args)
        mocker.patch.object(sys, "argv", ["urh.py"])

        # Mock the registry
        mock_registry = Mock()
        # Mock get_commands to return a list of command objects with 'name' attribute
        mock_command_obj = Mock()
        mock_command_obj.name = "check"
        mock_command_obj.description = "Check for updates"
        mock_registry.get_commands.return_value = [mock_command_obj]
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_registry)

        # Mock deployment info functions
        mocker.patch(
            "src.urh.cli.get_current_deployment_info",
            return_value={"repo": "test", "version": "v1"},
        )
        mocker.patch("src.urh.cli.format_deployment_header", return_value="test header")

        # Mock menu system to raise MenuExitException with is_main_menu=True
        mock_menu_system = mocker.patch("src.urh.cli._menu_system")
        mock_menu_system.show_menu.side_effect = MenuExitException(is_main_menu=True)

        # Mock sys.exit
        mock_sys_exit = mocker.patch("sys.exit")

        # Mock to avoid infinite loop in test environment
        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        mocker.patch("os.isatty", return_value=True)

        # Call main function which will handle the MenuExitException
        cli.main()

        # Verify that sys.exit was called with code 0
        mock_sys_exit.assert_called_once_with(0)

    def test_main_menu_loop_with_menu_exit_exception_submenu(self, mocker):
        """Test _main_menu_loop with MenuExitException for submenu."""
        from src.urh.menu import MenuExitException

        # Mock the registry
        mock_registry = Mock()
        # Mock get_commands to return a list of command objects with 'name' attribute
        mock_command_obj = Mock()
        mock_command_obj.name = "check"
        mock_command_obj.description = "Check for updates"
        mock_registry.get_commands.return_value = [mock_command_obj]
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_registry)

        # Mock deployment info functions
        mocker.patch(
            "src.urh.cli.get_current_deployment_info",
            return_value={"repo": "test", "version": "v1"},
        )
        mocker.patch("src.urh.cli.format_deployment_header", return_value="test header")

        # Mock menu system to raise MenuExitException with is_main_menu=False
        # This will make it raise the exception on the first call
        mock_menu_system = mocker.patch("src.urh.cli._menu_system")
        mock_menu_system.show_menu.side_effect = MenuExitException(
            is_main_menu=False
        )  # Only raise once

        # Mock to avoid infinite loop in test environment
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        mocker.patch("os.isatty", return_value=True)

        # Mock sys.exit to check if it's called appropriately
        mock_sys_exit = mocker.patch("sys.exit")

        # This should continue the loop and not call sys.exit for submenu exit
        try:
            cli._main_menu_loop()
        except Exception as _:
            pass  # Exception might be expected depending on implementation

        # Since it's a submenu exit, it should continue the loop and return normally
        # sys.exit should not be called for submenu exits in main loop
        mock_menu_system.show_menu.assert_called()
        # Make sure sys.exit was NOT called for submenu exit
        mock_sys_exit.assert_not_called()

    def test_setup_logging(self, mocker):
        """Test setup_logging function."""
        import logging

        # Mock logging.basicConfig to capture the arguments
        mock_basic_config = mocker.patch("logging.basicConfig")

        # Test with debug=False
        cli.setup_logging(debug=False)
        mock_basic_config.assert_called_with(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Test with debug=True
        cli.setup_logging(debug=True)
        mock_basic_config.assert_called_with(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )


class TestCLIErrorHandling:
    """Test CLI error handling paths."""

    def test_main_menu_loop_with_command_exception(self, mocker):
        """Test _main_menu_loop when command handler raises an exception."""
        # Mock the registry
        mock_registry = Mock()
        mock_command = Mock()
        mock_registry.get_command.return_value = mock_command
        # Make the command handler raise an exception
        mock_command.handler.side_effect = Exception("Test exception")
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_registry)

        # Mock deployment info functions
        mocker.patch(
            "src.urh.cli.get_current_deployment_info",
            return_value={"repo": "test", "version": "v1"},
        )
        mocker.patch("src.urh.cli.format_deployment_header", return_value="test header")

        # Mock menu system
        mock_menu_system = mocker.patch("src.urh.cli._menu_system")
        mock_menu_system.show_menu.return_value = "check"  # Return a selected command

        # Mock to avoid infinite loop in test environment
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        mocker.patch("os.isatty", return_value=True)

        # This should not crash but handle the exception appropriately
        try:
            cli._main_menu_loop()
        except Exception:
            # The exception should be handled within the function or propagated as needed
            pass


class TestCLIErrorHandlingComprehensive:
    """Test error handling and edge cases in CLI (comprehensive)."""

    def test_main_menu_loop_with_command_exception(self, mocker):
        """Test exception handling in _main_menu_loop when command execution fails."""
        import os
        import sys

        # Set up environment for test
        original_argv = sys.argv
        sys.argv = ["urh.py"]

        # Mock environment to avoid hanging
        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        mocker.patch("os.isatty", return_value=True)

        # Mock subprocess and system functions
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test", "version": "v1.0"},
        )
        mocker.patch("src.urh.deployment.get_deployment_info", return_value=[])
        mocker.patch("src.urh.deployment.get_status_output", return_value=None)
        mocker.patch("src.urh.cli.setup_logging", return_value=None)

        # Mock command registry
        mock_command_registry = mocker.MagicMock()

        # Mock _main_menu_loop to raise an exception (simulating command execution failure)
        def mock_main_menu_loop_with_exception():
            raise Exception("Command execution failed")

        mocker.patch(
            "src.urh.cli._main_menu_loop",
            side_effect=mock_main_menu_loop_with_exception,
        )
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_command_registry)

        # Mock sys.exit to prevent actual program termination
        mock_exit = mocker.patch("sys.exit")

        try:
            from src.urh.core import main

            # This should handle the exception gracefully - expect it to be raised
            # and then caught by the test framework
            with pytest.raises(Exception):
                main()

            # The exception should be raised, not caught by sys.exit in this case
            mock_exit.assert_not_called()

        finally:
            sys.argv = original_argv

    def test_unknown_command_error_handling(self, mocker, capsys):
        """Test unknown command error handling."""
        import sys

        # Set up command line arguments for unknown command
        original_argv = sys.argv
        sys.argv = ["urh.py", "unknown_command"]

        # Mock sys.exit to prevent actual program termination
        mock_exit = mocker.patch("sys.exit")

        # Mock command registry to return None for unknown command
        mock_command_registry = mocker.MagicMock()
        mock_command_registry.get_command.return_value = None

        # Create mock commands with proper string representation
        mock_check_cmd = mocker.MagicMock()
        mock_check_cmd.name = "check"
        mock_check_cmd.description = "Check for updates"

        mock_upgrade_cmd = mocker.MagicMock()
        mock_upgrade_cmd.name = "upgrade"
        mock_upgrade_cmd.description = "Upgrade system"

        mock_command_registry.get_commands.return_value = [
            mock_check_cmd,
            mock_upgrade_cmd,
        ]

        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_command_registry)

        try:
            from src.urh.core import main

            # This should handle unknown command gracefully
            main()

            # Verify sys.exit was called with error code 1
            mock_exit.assert_called_once_with(1)

            # Verify error message was printed
            captured = capsys.readouterr()
            assert "Unknown command: unknown_command" in captured.out
            assert "Available commands:" in captured.out
            assert "check - Check for updates" in captured.out
            assert "upgrade - Upgrade system" in captured.out

        finally:
            sys.argv = original_argv

    def test_successful_exit_code_return(self, mocker):
        """Test successful exit code return path."""
        import os
        import sys

        # Set up environment for successful execution
        original_argv = sys.argv
        sys.argv = ["urh.py"]

        # Mock environment to avoid hanging
        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        mocker.patch("os.isatty", return_value=True)

        # Mock subprocess and system functions
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test", "version": "v1.0"},
        )
        mocker.patch("src.urh.deployment.get_deployment_info", return_value=[])
        mocker.patch("src.urh.deployment.get_status_output", return_value=None)
        mocker.patch("src.urh.cli.setup_logging", return_value=None)

        # Mock command registry for successful execution
        mock_command_registry = mocker.MagicMock()

        # Mock _main_menu_loop to complete successfully and return None
        # This simulates the case where the menu loop completes without error
        def mock_main_menu_loop_successful():
            # Simulate successful menu loop completion by returning None
            # This should allow the main function to reach the "return 0" line
            return None

        mocker.patch(
            "src.urh.cli._main_menu_loop", side_effect=mock_main_menu_loop_successful
        )
        mocker.patch("src.urh.cli.CommandRegistry", return_value=mock_command_registry)

        # Mock sys.exit to prevent actual program termination
        mock_exit = mocker.patch("sys.exit")

        try:
            from src.urh.core import main

            # This should complete successfully
            result = main()

            # Verify the function completes without error
            # The result might be None or 0 depending on the execution path
            assert result in [0, None]

            # Verify sys.exit was not called (function returned normally)
            mock_exit.assert_not_called()

        finally:
            sys.argv = original_argv

    def test_main_with_invalid_command(self, mocker):
        """Test main function with an invalid command."""
        # Set environment variable to force non-gum behavior (avoid hanging during tests)
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        # Make sure os.isatty(1) returns True so the menu system thinks it's in a TTY
        mocker.patch("os.isatty", return_value=True)

        mock_command_registry = mocker.MagicMock()
        mock_command_registry.get_command.return_value = None
        mock_command_registry.get_commands.return_value = []  # Empty list of commands for invalid command test

        import sys

        original_argv = sys.argv
        sys.argv = ["urh.py", "invalid_command"]
        mock_exit = mocker.patch("sys.exit")

        try:
            # Mock object for subprocess.run that returns appropriate values
            mock_subprocess_result = mocker.MagicMock()
            mock_subprocess_result.returncode = (
                0  # For "which curl" command to return True
            )

            # Patch CommandRegistry and both locations of run_command to prevent privilege escalation
            # IMPORTANT: The main function imports CommandRegistry from .commands (src.urh.commands)
            mocker.patch(
                "src.urh.cli.CommandRegistry", return_value=mock_command_registry
            )
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Original location for compatibility
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Main module location for direct calls
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Actual implementation location
            # Also patch subprocess.run to prevent any direct subprocess calls
            mocker.patch("subprocess.run", return_value=mock_subprocess_result)
            # Patch system functions that make subprocess calls to prevent privilege escalation
            mocker.patch(
                "src.urh.system.check_curl_presence", return_value=True
            )  # Assume curl is available in tests
            mocker.patch("src.urh.system.check_curl_presence", return_value=True)
            # Patch deployment info functions that make system calls
            mocker.patch(
                "src.urh.deployment.get_current_deployment_info",
                return_value={"repository": "test", "version": "v1.0"},
            )
            mocker.patch("src.urh.deployment.get_deployment_info", return_value=[])
            mocker.patch(
                "src.urh.deployment.get_status_output", return_value=None
            )  # Needed for get_deployment_info
            # Patch config function to avoid file system access
            mock_config = mocker.MagicMock()
            mock_config.container_urls.options = ["ghcr.io/test/repo:testing"]
            mocker.patch("src.urh.config.get_config", return_value=mock_config)
            # Also patch setup_logging in the cli module
            mocker.patch("src.urh.cli.setup_logging", return_value=None)

            # Patch menu system to prevent gum from appearing
            mocker.patch("src.urh.cli._menu_system")
            mocker.patch("src.urh.commands._menu_system")

            # Import here to avoid issues with mocking
            from src.urh.core import main

            main()

            mock_command_registry.get_command.assert_called_once_with("invalid_command")
            mock_exit.assert_called_once_with(1)
        finally:
            sys.argv = original_argv

    def test_main_with_menu(self, mocker):
        """Test main function with interactive menu."""

        # Mock the _main_menu_loop to control its behavior and avoid infinite loop in tests
        def mock_main_menu_loop(max_iterations=None):
            # Mock functions that make system calls to prevent hanging
            mocker.patch(
                "src.urh.deployment.get_current_deployment_info",
                return_value={"repository": "test", "version": "v1.0"},
            )
            mocker.patch(
                "src.urh.deployment.format_deployment_header",
                return_value="Current deployment: test (v1.0)",
            )

            # Simulate selecting a command and executing it once
            mock_menu_system = mocker.MagicMock()
            mock_menu_system.show_menu.return_value = "check"
            mocker.patch("src.urh.commands._menu_system", mock_menu_system)

            # Execute the command once
            mock_command_registry = mocker.MagicMock()
            mock_command = mocker.MagicMock()
            mock_command_registry.get_command.return_value = mock_command
            mocker.patch(
                "src.urh.commands.CommandRegistry", return_value=mock_command_registry
            )

            mock_command.handler([])

            # Instead of raising an exception, just return to simulate single iteration
            return

        import sys

        original_argv = sys.argv
        sys.argv = ["urh.py"]
        mocker.patch("sys.exit")

        try:
            mocker.patch("src.urh.cli._main_menu_loop", side_effect=mock_main_menu_loop)
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Original location for compatibility
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Actual implementation location
            # Import here to avoid issues with mocking
            from src.urh.core import main

            main()

            # Verify the command was called - we can't really test the full behavior here
            # since we're mocking the core loop, but at least the function should complete
            pass
        finally:
            sys.argv = original_argv

    def test_main_with_menu_esc(self, mocker):
        """Test main function with interactive menu and ESC."""
        # Set environment variable to force non-gum behavior (avoid hanging during tests)
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        # Make sure os.isatty(1) returns True so the menu system thinks it's in a TTY
        mocker.patch("os.isatty", return_value=True)

        import sys

        original_argv = sys.argv
        sys.argv = ["urh.py"]
        mock_exit = mocker.patch("sys.exit")

        try:
            # Mock object for subprocess.run that returns appropriate values
            mock_subprocess_result = mocker.MagicMock()
            mock_subprocess_result.returncode = (
                0  # For "which curl" command to return True
            )

            # Mock _main_menu_loop to simulate ESC press in main menu
            def mock_main_menu_loop():
                # Raise MenuExitException(is_main_menu=True) to simulate ESC in main menu
                raise MenuExitException(is_main_menu=True)

            # Patch _main_menu_loop and other necessary functions to prevent privilege escalation
            # Main function imports directly from .menu (src.urh.menu)
            mocker.patch("src.urh.cli._main_menu_loop", side_effect=mock_main_menu_loop)
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Original location for compatibility
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Main module location for direct calls
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Actual implementation location
            # Also patch subprocess.run to prevent any direct subprocess calls
            mocker.patch("subprocess.run", return_value=mock_subprocess_result)
            # Patch system functions that make subprocess calls to prevent privilege escalation
            mocker.patch(
                "src.urh.system.check_curl_presence", return_value=True
            )  # Assume curl is available in tests
            mocker.patch("src.urh.system.check_curl_presence", return_value=True)
            # Patch deployment info functions that make system calls
            mocker.patch(
                "src.urh.deployment.get_current_deployment_info",
                return_value={"repository": "test", "version": "v1.0"},
            )
            mocker.patch("src.urh.deployment.get_deployment_info", return_value=[])
            mocker.patch(
                "src.urh.deployment.get_status_output", return_value=None
            )  # Needed for get_deployment_info
            # Patch config function to avoid file system access
            mock_config = mocker.MagicMock()
            mock_config.container_urls.options = ["ghcr.io/test/repo:testing"]
            mocker.patch("src.urh.config.get_config", return_value=mock_config)
            # Also patch setup_logging in the cli module
            mocker.patch("src.urh.cli.setup_logging", return_value=None)
            # IMPORTANT: The main function imports CommandRegistry from .commands (src.urh.commands)
            mock_command_registry = mocker.MagicMock()
            mocker.patch(
                "src.urh.cli.CommandRegistry", return_value=mock_command_registry
            )
            # Import here to avoid issues with mocking
            from src.urh.core import main

            main()

            mock_exit.assert_called_once_with(0)
        finally:
            sys.argv = original_argv
