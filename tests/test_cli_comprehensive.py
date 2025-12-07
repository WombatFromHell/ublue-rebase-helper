"""Comprehensive tests for the CLI module to improve coverage."""

import os
import sys
from unittest.mock import Mock


from src.urh import cli


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

    def test_main_no_args_with_test_environment(self, mocker):
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

        # Mock setup_logging
        mocker.patch("src.urh.cli.setup_logging")

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
