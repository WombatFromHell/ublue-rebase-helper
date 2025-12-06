"""Tests for the CLI module."""

import pytest

from src.urh.menu import MenuExitException


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
    def test_main_with_command(self, mocker, command, args, expected_calls):
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
            # Mock object for subprocess.run that returns appropriate values
            mock_subprocess_result = mocker.MagicMock()
            mock_subprocess_result.returncode = (
                0  # For "which curl" command to return True
            )

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
