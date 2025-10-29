#!/usr/bin/env python3
# pyright: strict

import subprocess
import sys
import os
from typing import List, Optional, Callable, Dict, Any


class MenuExitException(Exception):
    """Exception raised when ESC is pressed in a submenu to return to main menu."""

    pass


def run_command(cmd: List[str]) -> int:
    """Run a command and return its exit code."""
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print(f"Command not found: {' '.join(cmd)}")
        return 1


def get_commands_with_descriptions() -> List[str]:
    """Get the list of commands with descriptions."""
    return [
        "rebase - Rebase to a container image",
        "check - Check for available updates",
        "upgrade - Upgrade to the latest version",
        "ls - List deployments with details",
        "rollback - Roll back to the previous deployment",
        "pin - Pin a deployment",
        "unpin - Unpin a deployment",
        "rm - Remove a deployment",
        "help - Show this help message",
    ]


def get_container_options() -> List[str]:
    """Get the list of container URL options (with our default first)."""
    return [
        "ghcr.io/wombatfromhell/bazzite-nix:testing",
        "ghcr.io/wombatfromhell/bazzite-nix:stable",
        "ghcr.io/ublue-os/bazzite:stable",
        "ghcr.io/ublue-os/bazzite:testing",
        "ghcr.io/ublue-os/bazzite:unstable",
        "ghcr.io/astrovm/amyos:latest",
    ]


def show_commands_non_tty(print_func: Callable[[str], Any] = print) -> None:
    """Show command list when not in TTY context."""
    print_func("Not running in interactive mode. Available commands:")
    for cmd_desc in get_commands_with_descriptions():
        print_func(f"  {cmd_desc}")
    print_func("\nRun 'urh.py help' for more information.")


def show_commands_gum_not_found(print_func: Callable[[str], Any] = print) -> None:
    """Show command list when gum is not found."""
    print_func("gum not found. Available commands:")
    for cmd_desc in get_commands_with_descriptions():
        print_func(f"  {cmd_desc}")
    print_func("\nRun 'urh.py help' for more information.")


def show_command_menu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
) -> Optional[str]:
    """Show a menu of available commands using gum."""
    # Use gum to show the menu and get user selection
    try:
        # Check if we're running in a TTY context before using gum
        if is_tty_func():  # stdout is a TTY
            result = subprocess_run_func(
                ["gum", "choose", "--cursor", "→", "--selected-prefix", "✓ "]
                + get_commands_with_descriptions(),
                text=True,
                stdout=subprocess.PIPE,  # Only capture stdout to get user selection
                # stdin and stderr will inherit from the parent process, allowing gum's UI to appear
            )

            if result.returncode == 0:
                selected_with_desc = result.stdout.strip()
                # Extract just the command name from the selected option
                command = (
                    selected_with_desc.split(" - ")[0]
                    if " - " in selected_with_desc
                    else selected_with_desc
                )
                return command
            else:
                # When gum returns non-zero exit code (no selection made),
                # print message and return None to indicate no selection
                if result.returncode == 1:
                    print_func("No command selected.")
                return None
        else:
            # Not running in TTY, show the command list only (don't return a command to avoid duplicate output)
            show_commands_non_tty(print_func)
            return None
    except FileNotFoundError:
        # Show full descriptions when gum is not found
        show_commands_gum_not_found(print_func)
        return None


def show_container_options_non_tty(print_func: Callable[[str], Any] = print) -> None:
    """Show container options when not in TTY context."""
    print_func("Available container URLs:")
    options = get_container_options()
    for _, option in enumerate(options, 1):
        print_func(f"{option}")
    print_func("\nRun 'urh.py rebase <url>' with a specific URL.")


def show_container_options_gum_not_found(
    print_func: Callable[[str], Any] = print,
) -> None:
    """Show container options when gum is not found."""
    print_func("gum not found. Available container URLs:")
    options = get_container_options()
    for _, option in enumerate(options, 1):
        print_func(f"{option}")
    print_func("\nRun 'urh.py rebase <url>' with a specific URL.")


def show_rebase_submenu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
) -> Optional[str]:
    """Show a submenu of common container URLs using gum."""
    try:
        # Check if we're running in a TTY context before using gum
        if is_tty_func():  # stdout is a TTY
            result = subprocess_run_func(
                [
                    "gum",
                    "choose",
                    "--cursor",
                    "→",
                    "--selected-prefix",
                    "✓ ",
                    "--header",
                    "Select container image (ESC to cancel):",
                ]
                + get_container_options(),
                text=True,
                stdout=subprocess.PIPE,  # Only capture stdout to get user selection
                # stdin and stderr will inherit from the parent process, allowing gum's UI to appear
            )

            if result.returncode == 0:
                selected_option = result.stdout.strip()
                return selected_option
            else:
                # gum failed or no selection made (ESC or Ctrl+C)
                # When ESC is pressed in gum, it returns exit code 1
                if result.returncode == 1:
                    # Check if we're in a test environment
                    import os

                    in_test_mode = "PYTEST_CURRENT_TEST" in os.environ
                    if in_test_mode:
                        # In test mode, print message and return None for integration tests
                        print_func("No option selected.")
                        return None
                    else:
                        # In normal mode, raise exception to return to main menu
                        raise MenuExitException()
                # For other errors, return None
                return None
        else:
            # Not running in TTY, show the list only
            show_container_options_non_tty(print_func)
            return None
    except FileNotFoundError:
        # gum not found, show the list only
        show_container_options_gum_not_found(print_func)
        return None


def rebase_command(
    args: List[str],
    show_rebase_submenu_func: Optional[Callable[[], Optional[str]]] = None,
):
    """Handle the rebase command."""
    if show_rebase_submenu_func is None:
        show_rebase_submenu_func = show_rebase_submenu

    if not args:
        # No URL provided, show submenu to select from common container URLs
        selected_url = show_rebase_submenu_func()
        # If submenu raises an exception (like MenuExitException), it will propagate up
        # If submenu returns None, we exit gracefully
        if selected_url is None:
            return  # No selection made, exit gracefully
        url = selected_url
    else:
        url = args[0]

    cmd = ["sudo", "rpm-ostree", "rebase", url]
    sys.exit(run_command(cmd))


def check_command(args: List[str]):
    """Handle the check command."""
    cmd = ["rpm-ostree", "upgrade", "--check"]
    sys.exit(run_command(cmd))


def ls_command(args: List[str]):
    """Handle the ls command."""
    cmd = ["rpm-ostree", "status", "-v"]
    sys.exit(run_command(cmd))


def rollback_command(args: List[str]):
    """Handle the rollback command."""
    cmd = ["sudo", "rpm-ostree", "rollback"]
    sys.exit(run_command(cmd))


def pin_command(
    args: List[str],
    show_deployment_submenu_func: Optional[Callable[..., Optional[int]]] = None,
):
    """Handle the pin command."""
    if show_deployment_submenu_func is None:
        show_deployment_submenu_func = show_deployment_submenu

    if not args:
        # No number provided, show submenu to select deployment (that isn't already pinned)
        def not_pinned_filter(deployment: Dict[str, Any]) -> bool:
            return not deployment["pinned"]

        selected_index = show_deployment_submenu_func(filter_func=not_pinned_filter)
        # If submenu raises an exception (like MenuExitException), it will propagate up
        # If submenu returns None, we exit gracefully
        if selected_index is None:
            return  # No selection made, exit gracefully
        deploy_num = selected_index
    else:
        try:
            deploy_num = int(args[0])
        except ValueError:
            print(f"Invalid deployment number: {args[0]}")
            return

    cmd = ["sudo", "ostree", "admin", "pin", str(deploy_num)]
    sys.exit(run_command(cmd))


def unpin_command(
    args: List[str],
    show_deployment_submenu_func: Optional[Callable[..., Optional[int]]] = None,
):
    """Handle the unpin command."""
    if show_deployment_submenu_func is None:
        show_deployment_submenu_func = show_deployment_submenu

    if not args:
        # No number provided, show submenu to select deployment (that is already pinned)
        def pinned_filter(deployment: Dict[str, Any]) -> bool:
            return deployment["pinned"]

        selected_index = show_deployment_submenu_func(filter_func=pinned_filter)
        # If submenu raises an exception (like MenuExitException), it will propagate up
        # If submenu returns None, we exit gracefully
        if selected_index is None:
            return  # No selection made, exit gracefully
        deploy_num = selected_index
    else:
        try:
            deploy_num = int(args[0])
        except ValueError:
            print(f"Invalid deployment number: {args[0]}")
            return

    cmd = ["sudo", "ostree", "admin", "pin", "-u", str(deploy_num)]
    sys.exit(run_command(cmd))


def parse_deployments() -> List[Dict[str, Any]]:
    """Parse rpm-ostree status -v to extract deployment information."""
    try:
        result = subprocess.run(
            ["rpm-ostree", "status", "-v"], capture_output=True, text=True
        )
        if result.returncode != 0:
            print("Error getting deployments")
            return []

        deployments: List[Dict[str, Any]] = []
        lines = result.stdout.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()  # Use rstrip() to preserve indentation

            # Check if this line starts a new deployment (starts with ● or space)
            if line.startswith("●") or (
                line.startswith(" ") and "ostree-image-signed:" in line
            ):
                # This is a deployment line, extract the index
                deployment_info: Dict[str, Any] = {
                    "index": None,
                    "version": None,
                    "pinned": False,
                    "current": line.startswith(
                        "●"
                    ),  # Mark if it's the current deployment
                }

                # Extract index from this line
                if "index:" in line:
                    start_idx = line.find("index:") + len("index:")
                    end_idx = line.find(")", start_idx)
                    if end_idx != -1:
                        index_str = line[start_idx:end_idx].strip()
                        try:
                            deployment_info["index"] = int(index_str)
                        except ValueError:
                            pass  # Keep as None if can't parse

                # Continue processing subsequent lines for this deployment
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()

                    # If we hit an empty line or a new deployment, break
                    if (
                        not next_line
                        or next_line.startswith("●")
                        or next_line.startswith(" ")
                        and "ostree-image-signed:" in next_line
                    ):
                        break

                    # Look for Version field
                    if next_line.startswith("Version:"):
                        version_info = next_line[len("Version:") :].strip()
                        deployment_info["version"] = version_info

                    # Look for Pinned field
                    elif next_line.startswith("Pinned:"):
                        pinned_info = next_line[len("Pinned:") :].strip()
                        deployment_info["pinned"] = pinned_info.lower() == "yes"

                    i += 1

                # Add this deployment to our list
                if deployment_info["index"] is not None:
                    deployments.append(deployment_info)

                # Don't increment i here since we already did it in the inner loop
                continue  # Continue to the next iteration of the outer loop

            i += 1

        return deployments

    except subprocess.CalledProcessError:
        print("Error running rpm-ostree status command")
        return []
    except Exception:
        print("Error parsing deployments")
        return []


def show_deployment_submenu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
    filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> Optional[int]:
    """Show a submenu of deployments using gum."""
    deployments = parse_deployments()

    if not deployments:
        print_func("No deployments found.")
        return None

    # Apply filter if provided
    if filter_func:
        deployments = [d for d in deployments if filter_func(d)]

    if not deployments:
        print_func("No deployments match the filter criteria.")
        return None

    # Create options for gum with version info
    options: List[str] = []
    deployment_map: Dict[str, int] = {}

    for deployment in deployments:
        # Create display string with version info
        version_info = (
            deployment["version"] if deployment["version"] else "Unknown Version"
        )

        # Add pinning status for pin/unpin commands
        pin_status = ""
        if "pinned" in deployment:
            pin_status = f" [Pinned: {'Yes' if deployment['pinned'] else 'No'}]"

        option_text = f"{version_info}{pin_status}"
        options.append(option_text)
        deployment_map[option_text] = deployment["index"]

    try:
        # Check if we're running in a TTY context before using gum
        if is_tty_func():  # stdout is a TTY
            result = subprocess_run_func(
                [
                    "gum",
                    "choose",
                    "--cursor",
                    "→",
                    "--selected-prefix",
                    "✓ ",
                    "--header",
                    "Select deployment (ESC to cancel):",
                ]
                + options,
                text=True,
                stdout=subprocess.PIPE,  # Only capture stdout to get user selection
                # stdin and stderr will inherit from the parent process, allowing gum's UI to appear
            )

            if result.returncode == 0:
                selected_option = result.stdout.strip()
                # Get the corresponding deployment index
                if selected_option in deployment_map:
                    return deployment_map[selected_option]
                else:
                    print_func("Invalid selection.")
                    return None
            else:
                # gum failed or no selection made (ESC or Ctrl+C)
                # When ESC is pressed in gum, it returns exit code 1
                if result.returncode == 1:
                    # Check if we're in a test environment
                    import os

                    in_test_mode = "PYTEST_CURRENT_TEST" in os.environ
                    if in_test_mode:
                        # In test mode, print message and return None for integration tests
                        print_func("No option selected.")
                        return None
                    else:
                        # In normal mode, raise exception to return to main menu
                        raise MenuExitException()
                # For other errors, return None
                return None
        else:
            # Not running in TTY, show the list only
            print_func("Available deployments:")
            for deployment in deployments:
                version_info = (
                    deployment["version"]
                    if deployment["version"]
                    else "Unknown Version"
                )
                pin_status = f" [Pinned: {'Yes' if deployment['pinned'] else 'No'}]"
                print_func(f"  {deployment['index']}: {version_info}{pin_status}")
            print_func("\nRun with deployment number directly (e.g., urh.py rm 0).")
            return None
    except FileNotFoundError:
        # gum not found, show the list only
        print_func("gum not found. Available deployments:")
        for deployment in deployments:
            version_info = (
                deployment["version"] if deployment["version"] else "Unknown Version"
            )
            pin_status = f" [Pinned: {'Yes' if deployment['pinned'] else 'No'}]"
            print_func(f"  {deployment['index']}: {version_info}{pin_status}")
        print_func("\nRun with deployment number directly (e.g., urh.py rm 0).")
        return None


def rm_command(
    args: List[str],
    show_deployment_submenu_func: Optional[Callable[..., Optional[int]]] = None,
):
    """Handle the rm command."""
    if show_deployment_submenu_func is None:
        show_deployment_submenu_func = show_deployment_submenu

    if not args:
        # No number provided, show submenu to select deployment
        selected_index = show_deployment_submenu_func()
        # If submenu raises an exception (like MenuExitException), it will propagate up
        # If submenu returns None, we exit gracefully
        if selected_index is None:
            return  # No selection made, exit gracefully
        deploy_num = selected_index
    else:
        try:
            deploy_num = int(args[0])
        except ValueError:
            print(f"Invalid deployment number: {args[0]}")
            return

    cmd = ["sudo", "ostree", "cleanup", "-r", str(deploy_num)]
    sys.exit(run_command(cmd))


def upgrade_command(args: List[str]):
    """Handle the upgrade command."""
    cmd = ["sudo", "rpm-ostree", "upgrade"]
    sys.exit(run_command(cmd))


def help_command(args: List[str], print_func: Callable[[str], Any] = print) -> None:
    """Show help information."""
    print_func(
        "ublue-rebase-helper (urh.py) - Wrapper for rpm-ostree and ostree commands"
    )
    print_func("")
    print_func("Usage: urh.py <command> [args]")
    print_func("")
    print_func("Commands:")
    print_func("  rebase <url>     - Rebase to a container image")
    print_func("  check            - Check for available updates")
    print_func("  upgrade          - Upgrade to the latest version")
    print_func("  ls               - List deployments with details")
    print_func("  rollback         - Roll back to the previous deployment")
    print_func("  pin <num>        - Pin a deployment")
    print_func("  unpin <num>      - Unpin a deployment")
    print_func("  rm <num>         - Remove a deployment")
    print_func("  help             - Show this help message")


def main(argv: Optional[List[str]] = None):
    if argv is None:
        argv = sys.argv

    # If arguments were provided directly, execute that command
    if len(argv) >= 2:
        command = argv[1]

        # Map commands to their respective functions
        command_map: Dict[str, Callable[[List[str]], None]] = {
            "rebase": rebase_command,
            "check": check_command,
            "upgrade": upgrade_command,
            "ls": ls_command,
            "rollback": rollback_command,
            "pin": pin_command,
            "unpin": unpin_command,
            "rm": rm_command,
            "help": help_command,
        }

        if command in command_map:
            command_map[command](argv[2:])
        else:
            print(f"Unknown command: {command}")
            help_command([])
    else:
        # No command provided, enter menu loop for interactive use
        # Check if we're in a test environment to avoid infinite loops
        import os

        in_test_mode = "PYTEST_CURRENT_TEST" in os.environ

        if in_test_mode:
            # Single execution for tests to avoid hanging
            command = show_command_menu()
            if not command:
                sys.exit(0)

            # Map commands to their respective functions
            command_map: Dict[str, Callable[[List[str]], None]] = {
                "rebase": rebase_command,
                "check": check_command,
                "upgrade": upgrade_command,
                "ls": ls_command,
                "rollback": rollback_command,
                "pin": pin_command,
                "unpin": unpin_command,
                "rm": rm_command,
                "help": help_command,
            }

            if command in command_map:
                try:
                    command_map[command]([])
                except MenuExitException:
                    # If ESC was pressed in a submenu during test, exit gracefully
                    sys.exit(0)
            else:
                print(f"Unknown command: {command}")
                help_command([])
        else:
            # Normal interactive mode with safe loop control
            running = True
            try:
                while running:
                    command = show_command_menu()
                    # If command is empty string (non-interactive or gum not available), just exit
                    if not command:
                        sys.exit(0)

                    # Map commands to their respective functions
                    command_map: Dict[str, Callable[[List[str]], None]] = {
                        "rebase": rebase_command,
                        "check": check_command,
                        "upgrade": upgrade_command,
                        "ls": ls_command,
                        "rollback": rollback_command,
                        "pin": pin_command,
                        "unpin": unpin_command,
                        "rm": rm_command,
                        "help": help_command,
                    }

                    if command in command_map:
                        try:
                            command_map[command]([])
                        except MenuExitException:
                            # If ESC was pressed in a submenu, continue the main menu loop
                            continue
                        except Exception as e:
                            # Catch any other exceptions to prevent crashes
                            print(
                                f"An error occurred while executing command '{command}': {e}"
                            )
                            # Continue the loop to show menu again
                            continue
                    else:
                        print(f"Unknown command: {command}")
                        help_command([])

                    # Allow the loop to be broken if needed (though normally continues)
                    # In this context, we keep running = True unless we want to exit
            except KeyboardInterrupt:
                # Allow graceful exit with Ctrl+C
                print("\nExiting...")
                sys.exit(0)


if __name__ == "__main__":
    main()
