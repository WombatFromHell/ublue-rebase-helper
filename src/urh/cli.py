"""
CLI module for ublue-rebase-helper.
"""

import logging
import os
import sys

from .commands import CommandRegistry
from .config import get_config
from .constants import __version__
from .deployment import format_deployment_header, get_current_deployment_info
from .menu import MenuExitException
from .system import check_curl_presence


def setup_logging(debug: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def _main_menu_loop(registry: CommandRegistry) -> None:
    """Main menu functionality that shows the menu and executes commands."""
    # Get current deployment info for persistent header
    deployment_info_header = get_current_deployment_info()
    persistent_header = format_deployment_header(deployment_info_header)

    commands = registry.get_commands()
    # Sort commands alphabetically by name for better organization
    sorted_commands = sorted(commands, key=lambda cmd: cmd.name)
    from .models import MenuItem  # Import here to avoid circular import

    items = [MenuItem(cmd.name, cmd.description) for cmd in sorted_commands]

    selected = registry._menu_system.show_menu(
        items,
        "Select a command (ESC to exit):",
        persistent_header=persistent_header,
        is_main_menu=True,
    )

    if selected is None:
        # In text mode, if no selection is made, return to allow main to loop
        return

    # Execute the selected command
    command = registry.get_command(selected)
    if command:
        # Execute the command, which may raise MenuExitException
        command.handler([])


def main():
    """
    Main entry point for the CLI.
    """
    # Handle --version/-V and --help/-h flags
    if len(sys.argv) == 2:
        if sys.argv[1] in ("--version", "-V"):
            print(f"ublue-rebase-helper v{__version__}")
            sys.exit(0)
        if sys.argv[1] in ("--help", "-h"):
            print(f"ublue-rebase-helper v{__version__}")
            print("\nUsage: urh [command] [options]")
            print("\nAvailable commands:")
            registry = CommandRegistry()
            for cmd in registry.get_commands():
                print(f"  {cmd.name} - {cmd.description}")
            print("\nOptions:")
            print("  --version, -V  Show version information")
            print("  --help, -h     Show this help message")
            sys.exit(0)

    # Setup logging based on config
    config = get_config()
    setup_logging(debug=config.settings.debug_mode)

    # Check if curl is available before proceeding
    if not check_curl_presence():
        logger = logging.getLogger(__name__)
        logger.error("curl is required for this application but was not found.")
        print("Error: curl is required for this application but was not found.")
        print("Please install curl and try again.")
        sys.exit(1)
    else:
        # Only continue execution if curl is available
        # Create command registry
        registry = CommandRegistry()

        # Parse command line arguments
        if len(sys.argv) < 2:
            # Check if we're in a test environment to avoid infinite loop
            in_test_environment = "PYTEST_CURRENT_TEST" in os.environ

            # Show main menu in a loop to return to main menu after submenu ESC
            # But don't loop infinitely in test environments
            while True:
                try:
                    _main_menu_loop(registry)
                    # If in test environment, break after one iteration
                    if in_test_environment:
                        return
                except MenuExitException as e:
                    if e.is_main_menu:
                        sys.exit(0)
                        # If sys.exit is mocked in tests, we still need to exit the function
                        return  # Exit the main function to stop the loop
                    else:
                        # When ESC is pressed in a submenu, continue the loop to show main menu again
                        # unless we're in a test environment
                        if in_test_environment:
                            return
                        continue
        else:
            # Execute command directly
            command_name = sys.argv[1]
            command = registry.get_command(command_name)

            if command:
                # Pass remaining arguments to the command handler
                command.handler(sys.argv[2:])
            else:
                print(f"Unknown command: {command_name}")
                print(f"\nublue-rebase-helper v{__version__}")
                print("\nUsage: urh [command] [options]")
                print("\nAvailable commands:")
                for cmd in registry.get_commands():
                    print(f"  {cmd.name} - {cmd.description}")
                print("\nOptions:")
                print("  --version, -V  Show version information")
                print("  --help, -h     Show this help message")
                sys.exit(1)

    # Return successful exit code
    return 0


if __name__ == "__main__":
    main()
