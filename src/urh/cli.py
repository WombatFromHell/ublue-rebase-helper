"""
CLI module for ublue-rebase-helper.
"""

import logging
import sys
from typing import List, Optional

from .commands.registry import CommandRegistry
from .config import get_config
from .constants import __version__, format_version_header
from .deployment import (
    format_menu_header,
    get_current_deployment_info,
)
from .menu import MenuExitException
from .system import check_curl_presence


def setup_logging(debug: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def _show_help() -> None:
    """Display help message with available commands and options."""
    print(f"ublue-rebase-helper v{__version__}")
    print("\nUsage: urh [command] [options]")
    print("\nAvailable commands:")
    registry = CommandRegistry()
    for cmd in registry.get_commands():
        print(f"  {cmd.name} - {cmd.description}")
    print("\nOptions:")
    print("  --version, -V  Show version information")
    print("  --help, -h     Show this help message")
    print("  -y, --yes      Skip confirmation prompts (for rebase command)")


def _handle_version_flag() -> bool:
    """Check for --version/-V flag. Returns True if flag was handled."""
    if len(sys.argv) == 2 and sys.argv[1] in ("--version", "-V"):
        print(f"ublue-rebase-helper v{__version__}")
        return True
    return False


def _handle_help_flag() -> bool:
    """Check for --help/-h flag. Returns True if flag was handled."""
    if len(sys.argv) == 2 and sys.argv[1] in ("--help", "-h"):
        _show_help()
        return True
    return False


def _check_dependencies() -> Optional[CommandRegistry]:
    """Check dependencies and return registry, or exit if missing.

    Returns:
        CommandRegistry instance if curl is available, None otherwise.
    """
    config = get_config()
    setup_logging(debug=config.settings.debug_mode)

    if not check_curl_presence():
        logger = logging.getLogger(__name__)
        logger.error("curl is required for this application but was not found.")
        print("Error: curl is required for this application but was not found.")
        print("Please install curl and try again.")
        return None

    return CommandRegistry()


def _execute_command(
    registry: CommandRegistry, command_name: str, command_args: List[str]
) -> int:
    """Execute a command by name with given arguments.

    Returns:
        Exit code from command handler.
    """
    # Parse global flags like -y/--yes
    skip_confirmation = False
    if "-y" in command_args or "--yes" in command_args:
        skip_confirmation = True
        command_args = [arg for arg in command_args if arg not in ("-y", "--yes")]

    command = registry.get_command(command_name)

    if command:
        if command_name == "rebase":
            return command.handler(
                command_args,
                skip_confirmation=skip_confirmation,  # type: ignore[unknown-argument]
            )
        else:
            return command.handler(command_args)
    else:
        print(f"Unknown command: {command_name}")
        _show_help()
        return 1


def _main_menu_loop(registry: CommandRegistry) -> int:
    """Main menu functionality that shows the menu and executes commands."""
    # Get current deployment info for persistent header
    deployment_info = get_current_deployment_info()
    version_header = format_version_header()
    persistent_header = format_menu_header(version_header, deployment_info)

    commands = registry.get_commands()
    # Sort commands alphabetically by name for better organization
    sorted_commands = sorted(commands, key=lambda cmd: cmd.name)
    from .models import MenuItem  # Import here to avoid circular import

    items = [MenuItem(cmd.name, cmd.description) for cmd in sorted_commands]

    while True:
        selected = registry._menu_system.show_menu(
            items,
            "Select a command (ESC to exit):",
            persistent_header=persistent_header,
            is_main_menu=True,
        )

        if selected is None:
            # In text mode, if no selection is made, return to allow main to loop
            return 0

        # Execute the selected command
        command = registry.get_command(selected)
        if command:
            try:
                # Execute the command
                result = command.handler([])
                # Command completed successfully, exit the menu loop
                return result
            except MenuExitException as e:
                # ESC pressed in submenu, return to main menu
                if not e.is_main_menu:
                    continue
                raise  # ESC in main menu, exit
        return 0


def main():
    """Main entry point for the CLI."""
    # Handle --version/-V and --help/-h flags
    if _handle_version_flag():
        return 0
    if _handle_help_flag():
        return 0

    # Check dependencies
    registry = _check_dependencies()
    if registry is None:
        return 1

    # Parse command line arguments
    if len(sys.argv) < 2:
        try:
            return _main_menu_loop(registry)
        except MenuExitException:
            return 0
    else:
        return _execute_command(registry, sys.argv[1], sys.argv[2:])


if __name__ == "__main__":
    main()
